import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface LlmResponse {
  punkte: number;
  max_punkte: number;
  feedback: string;
  details: Record<string, unknown>;
  provider: string;
  model: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  dauer_ms: number;
}

interface GradeRequest {
  antwortId: number;
  provider: 'ollama' | 'openai';
  model?: string;
  /** Base64-encoded image for diagram grading */
  image?: string;
}

@Injectable()
export class BewertungService {
  private readonly logger = new Logger(BewertungService.name);

  constructor(private readonly prisma: PrismaService) {}

  /* ═══════════════ PUBLIC API ═══════════════ */

  /** Grade a single answer */
  async bewerten(req: GradeRequest): Promise<LlmResponse> {
    // 1. Load answer + exam info
    const antwort = await this.prisma.antworten.findUniqueOrThrow({
      where: { id: req.antwortId },
      include: {
        pruefungen: true,
        antwort_bilder: { orderBy: { sortierung: 'asc' } },
      },
    });

    // 2. Find matching model solution
    const musterloesung = await this.prisma.musterloesungen.findFirst({
      where: {
        pruefung_id: antwort.pruefung_id,
        aufgabe: this.normalizeAufgabe(antwort.aufgabe),
      },
    });

    // 3. Build the prompt
    const prompt = this.buildPrompt(
      antwort.aufgabe,
      antwort.antwort_text,
      musterloesung?.erwartung_text || null,
      Number(antwort.max_punkte || musterloesung?.max_punkte || 10),
      (antwort as any).pruefungen.zeitraum_label,
    );

    // 4. Call LLM
    const model = req.model || (req.provider === 'ollama' ? 'llama3.2:3b' : 'gpt-4o-mini');
    const start = Date.now();
    let result: LlmResponse;

    if (req.provider === 'ollama') {
      result = await this.callOllama(prompt, model, req.image);
    } else {
      result = await this.callOpenAI(prompt, model, req.image);
    }

    result.dauer_ms = Date.now() - start;

    // 5. Save to DB
    await this.prisma.bewertungen.upsert({
      where: {
        antwort_id_llm_provider: {
          antwort_id: req.antwortId,
          llm_provider: req.provider,
        },
      },
      create: {
        antwort_id: req.antwortId,
        punkte: result.punkte,
        max_punkte: result.max_punkte,
        feedback: result.feedback,
        bewertung_details: result.details as any,
        llm_provider: result.provider,
        llm_model: result.model,
        prompt_tokens: result.prompt_tokens,
        completion_tokens: result.completion_tokens,
        dauer_ms: result.dauer_ms,
      },
      update: {
        punkte: result.punkte,
        max_punkte: result.max_punkte,
        feedback: result.feedback,
        bewertung_details: result.details as any,
        llm_model: result.model,
        prompt_tokens: result.prompt_tokens,
        completion_tokens: result.completion_tokens,
        dauer_ms: result.dauer_ms,
      },
    });

    // 6. Also update the antwort's punkte if not yet set
    if (antwort.punkte == null) {
      await this.prisma.antworten.update({
        where: { id: req.antwortId },
        data: {
          punkte: result.punkte,
          max_punkte: result.max_punkte,
        },
      });
    }

    return result;
  }

  /** Grade all ungraded answers of a specific exam */
  async bewertenPruefung(
    pruefungId: number,
    provider: 'ollama' | 'openai',
    model?: string,
  ) {
    const antworten = await this.prisma.antworten.findMany({
      where: {
        pruefung_id: pruefungId,
        durchlauf: 1,
        punkte: null,
        antwort_text: { not: '' },
        aufgabe: { not: { startsWith: 'KEY_' } },
      },
    });

    const results: Array<{ aufgabe: string; punkte: number; feedback: string }> = [];

    for (const a of antworten) {
      if (a.antwort_text.includes('(noch nicht beantwortet)')) continue;
      try {
        const r = await this.bewerten({
          antwortId: a.id,
          provider,
          model,
        });
        results.push({
          aufgabe: a.aufgabe,
          punkte: r.punkte,
          feedback: r.feedback,
        });
      } catch (e) {
        this.logger.error(`Fehler bei Aufgabe ${a.aufgabe}: ${e}`);
        results.push({
          aufgabe: a.aufgabe,
          punkte: -1,
          feedback: `Fehler: ${e}`,
        });
      }
    }

    return {
      pruefung_id: pruefungId,
      bewertet: results.filter((r) => r.punkte >= 0).length,
      fehler: results.filter((r) => r.punkte < 0).length,
      ergebnisse: results,
    };
  }

  /** Get existing bewertungen for an answer */
  findByAntwort(antwortId: number) {
    return this.prisma.bewertungen.findMany({
      where: { antwort_id: antwortId },
      orderBy: { erstellt_am: 'desc' },
    });
  }

  /** Get all bewertungen for a pruefung */
  findByPruefung(pruefungId: number) {
    return this.prisma.bewertungen.findMany({
      where: {
        antworten: { pruefung_id: pruefungId },
      },
      include: {
        antworten: { select: { aufgabe: true, antwort_text: true } },
      },
      orderBy: { erstellt_am: 'desc' },
    });
  }

  /** Get all musterloesungen for a pruefung */
  findMusterloesungen(pruefungId: number) {
    return this.prisma.musterloesungen.findMany({
      where: { pruefung_id: pruefungId },
      orderBy: { aufgabe: 'asc' },
    });
  }

  /** Check LLM provider availability */
  async checkProvider(provider: 'ollama' | 'openai'): Promise<{
    available: boolean;
    models?: string[];
    error?: string;
  }> {
    if (provider === 'ollama') {
      return this.checkOllama();
    }
    return this.checkOpenAI();
  }

  /* ═══════════════ PROMPT BUILDING ═══════════════ */

  private buildPrompt(
    aufgabe: string,
    antwort: string,
    musterloesung: string | null,
    maxPunkte: number,
    pruefung: string,
  ): string {
    const musterBlock = musterloesung
      ? `\n## Musterlösung / Erwartungshorizont:\n${musterloesung}\n`
      : '\n(Keine Musterlösung verfügbar - bewerte nach fachlicher Korrektheit)\n';

    return `Du bist ein erfahrener IHK-Prüfer für die Abschlussprüfung Teil 2 (FIAE - Fachinformatiker Anwendungsentwicklung).

## Prüfung: ${pruefung}
## Aufgabe: ${aufgabe}
## Maximale Punktzahl: ${maxPunkte}
${musterBlock}
## Antwort des Prüflings:
${antwort}

## Deine Aufgabe:
Bewerte die Antwort des Prüflings anhand der Musterlösung. Berücksichtige dabei:
1. **Inhaltliche Korrektheit**: Stimmen die Kernaussagen überein? Synonyme und Umformulierungen sind erlaubt.
2. **Vollständigkeit**: Wurden alle erwarteten Punkte genannt?
3. **Fachliche Tiefe**: Zeigt der Prüfling Verständnis?
4. **Teilpunkte**: Vergib Teilpunkte für teilweise richtige Antworten.

WICHTIG: Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein anderer Text!):
{
  "punkte": <number zwischen 0 und ${maxPunkte}>,
  "max_punkte": ${maxPunkte},
  "feedback": "<kurze deutschsprachige Begründung der Bewertung, max 3 Sätze>",
  "korrekte_aspekte": ["<was richtig war>"],
  "fehlende_aspekte": ["<was gefehlt hat>"],
  "konfidenz": <0.0-1.0 wie sicher du dir bei der Bewertung bist>
}`;
  }

  /* ═══════════════ OLLAMA ═══════════════ */

  private async callOllama(
    prompt: string,
    model: string,
    image?: string,
  ): Promise<LlmResponse> {
    const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434';

    const body: Record<string, unknown> = {
      model,
      prompt,
      stream: false,
      options: {
        temperature: 0.1,
        num_predict: 1024,
      },
    };

    // Vision: add image if present
    if (image) {
      body.images = [image];
    }

    // 5 min timeout for CPU-only inference
    const resp = await fetch(`${ollamaUrl}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(300_000),
    });

    if (!resp.ok) {
      throw new Error(`Ollama error: ${resp.status} ${await resp.text()}`);
    }

    const data = (await resp.json()) as {
      response: string;
      eval_count?: number;
      prompt_eval_count?: number;
    };

    const parsed = this.parseJsonResponse(data.response);

    return {
      punkte: parsed.punkte,
      max_punkte: parsed.max_punkte,
      feedback: parsed.feedback,
      details: parsed,
      provider: 'ollama',
      model,
      prompt_tokens: data.prompt_eval_count,
      completion_tokens: data.eval_count,
      dauer_ms: 0,
    };
  }

  private async checkOllama(): Promise<{
    available: boolean;
    models?: string[];
    error?: string;
  }> {
    try {
      const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434';
      const resp = await fetch(`${ollamaUrl}/api/tags`, {
        signal: AbortSignal.timeout(3000),
      });
      if (!resp.ok) throw new Error(`Status ${resp.status}`);
      const data = (await resp.json()) as {
        models: Array<{ name: string }>;
      };
      return {
        available: true,
        models: data.models.map((m) => m.name),
      };
    } catch (e) {
      return { available: false, error: `Ollama nicht erreichbar: ${e}` };
    }
  }

  /* ═══════════════ OPENAI ═══════════════ */

  private async callOpenAI(
    prompt: string,
    model: string,
    image?: string,
  ): Promise<LlmResponse> {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) throw new Error('OPENAI_API_KEY nicht gesetzt (in .env)');

    const messages: Array<Record<string, unknown>> = [];

    if (image) {
      // Vision request
      messages.push({
        role: 'user',
        content: [
          { type: 'text', text: prompt },
          {
            type: 'image_url',
            image_url: { url: `data:image/png;base64,${image}`, detail: 'high' },
          },
        ],
      });
    } else {
      messages.push({ role: 'user', content: prompt });
    }

    const resp = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.1,
        max_tokens: 1024,
        response_format: { type: 'json_object' },
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`OpenAI error: ${resp.status} ${errText}`);
    }

    const data = (await resp.json()) as {
      choices: Array<{ message: { content: string } }>;
      usage?: { prompt_tokens: number; completion_tokens: number };
    };

    const content = data.choices[0]?.message?.content || '{}';
    const parsed = this.parseJsonResponse(content);

    return {
      punkte: parsed.punkte,
      max_punkte: parsed.max_punkte,
      feedback: parsed.feedback,
      details: parsed,
      provider: 'openai',
      model,
      prompt_tokens: data.usage?.prompt_tokens,
      completion_tokens: data.usage?.completion_tokens,
      dauer_ms: 0,
    };
  }

  private async checkOpenAI(): Promise<{
    available: boolean;
    models?: string[];
    error?: string;
  }> {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return { available: false, error: 'OPENAI_API_KEY nicht in .env gesetzt' };
    }
    try {
      const resp = await fetch('https://api.openai.com/v1/models', {
        headers: { Authorization: `Bearer ${apiKey}` },
        signal: AbortSignal.timeout(5000),
      });
      if (!resp.ok) throw new Error(`Status ${resp.status}`);
      const data = (await resp.json()) as {
        data: Array<{ id: string }>;
      };
      const relevant = data.data
        .filter((m) => m.id.includes('gpt'))
        .map((m) => m.id)
        .sort();
      return { available: true, models: relevant };
    } catch (e) {
      return { available: false, error: `OpenAI nicht erreichbar: ${e}` };
    }
  }

  /* ═══════════════ HELPERS ═══════════════ */

  /**
   * Normalize aufgabe key to match musterloesung format.
   * Student answers: "1a", "2b", "3"  →  Musterlösung: "1", "1.a", "2.b"
   */
  private normalizeAufgabe(aufgabe: string): string {
    // Try exact match first, then with dot notation
    const match = aufgabe.match(/^(\d+)([a-z])$/i);
    if (match) {
      return `${match[1]}.${match[2].toLowerCase()}`;
    }
    // "1.1" → "1" (parent aufgabe)
    return aufgabe;
  }

  /** Parse JSON from LLM output (handles markdown code blocks) */
  private parseJsonResponse(text: string): {
    punkte: number;
    max_punkte: number;
    feedback: string;
    [key: string]: unknown;
  } {
    // Remove markdown code block wrapper if present
    let cleaned = text.trim();
    const jsonMatch = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      cleaned = jsonMatch[1].trim();
    }

    // Find JSON object
    const start = cleaned.indexOf('{');
    const end = cleaned.lastIndexOf('}');
    if (start === -1 || end === -1) {
      this.logger.warn(`LLM returned non-JSON: ${text.substring(0, 200)}`);
      return {
        punkte: 0,
        max_punkte: 0,
        feedback: 'Bewertung konnte nicht geparst werden: ' + text.substring(0, 200),
      };
    }

    try {
      const parsed = JSON.parse(cleaned.substring(start, end + 1));
      return {
        punkte: Number(parsed.punkte) || 0,
        max_punkte: Number(parsed.max_punkte) || 0,
        feedback: String(parsed.feedback || ''),
        ...parsed,
      };
    } catch (e) {
      this.logger.warn(`JSON parse error: ${e}`);
      return {
        punkte: 0,
        max_punkte: 0,
        feedback: 'JSON-Parse-Fehler: ' + text.substring(0, 200),
      };
    }
  }
}

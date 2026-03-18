import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';

const WORKSPACE_ROOT = join(__dirname, '..', '..', '..');

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
  provider: 'ollama' | 'openai' | 'perplexity';
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
        pruefung: true,
        bilder: { orderBy: { sortierung: 'asc' } },
      },
    });

    // 2. Find matching model solution
    const musterloesung = await this.prisma.musterloesungen.findFirst({
      where: {
        pruefung_id: antwort.pruefung_id,
        aufgabe: this.normalizeAufgabe(antwort.aufgabe),
      },
    });

    // 3. Bilder laden (handschriftliche Lösungen / Diagramme)
    const images: string[] = [];
    if (req.image) {
      images.push(req.image);
    }
    // Automatisch hochgeladene Bilder als Base64 laden
    if ((antwort as any).bilder?.length) {
      for (const bild of (antwort as any).bilder) {
        try {
          const filePath = join(WORKSPACE_ROOT, bild.storage_pfad);
          if (existsSync(filePath)) {
            const buf = readFileSync(filePath);
            images.push(buf.toString('base64'));
          }
        } catch (e) {
          this.logger.warn(`Bild ${bild.dateiname} konnte nicht geladen werden: ${e}`);
        }
      }
    }

    const hasImages = images.length > 0;
    const hasText = !!antwort.antwort_text?.trim();

    // 4. Build the prompt
    const prompt = this.buildPrompt(
      antwort.aufgabe,
      hasText ? antwort.antwort_text : '(Antwort als Bild/Scan beigefügt – siehe Bilder)',
      musterloesung?.erwartung_text || null,
      Number(antwort.max_punkte || musterloesung?.max_punkte || 10),
      (antwort as any).pruefung.zeitraum_label,
      hasImages,
    );

    // 5. Call LLM – für Vision ein Vision-fähiges Modell wählen
    let model = req.model;
    if (!model) {
      if (req.provider === 'ollama') {
        model = hasImages ? 'llama3.2-vision:11b' : 'llama3.2:3b';
      } else if (req.provider === 'perplexity') {
        model = 'sonar-pro';
      } else {
        model = hasImages ? 'gpt-4o' : 'gpt-4o-mini';
      }
    }
    const start = Date.now();
    let result: LlmResponse;

    if (req.provider === 'ollama') {
      result = await this.callOllama(prompt, model, hasImages ? images : undefined);
    } else if (req.provider === 'perplexity') {
      result = await this.callPerplexity(prompt, model);
    } else {
      result = await this.callOpenAI(prompt, model, hasImages ? images : undefined);
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

  /** Analyse a document's OCR text and extract structured aufgaben + answers using LLM */
  async analyseDokumentOcr(
    dokumentId: number,
    provider: 'ollama' | 'openai' | 'perplexity',
    model?: string,
    ocrText?: string,
  ): Promise<{
    aufgaben: Array<{ aufgabe: string; antwort: string; max_punkte?: number }>;
    provider: string;
    model: string;
    dauer_ms: number;
    ocr_chars: number;
  }> {
    // 1. Get document info
    const dokument = await this.prisma.dokumente.findUnique({
      where: { id: dokumentId },
      include: { pruefung: true },
    });
    if (!dokument) throw new Error(`Dokument ${dokumentId} nicht gefunden`);

    // 2. If no OCR text provided, run OCR via Python script
    if (!ocrText) {
      const { execFile } = await import('child_process');
      const ocrResult = await new Promise<any>((resolve, reject) => {
        execFile(
          join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe'),
          [join(WORKSPACE_ROOT, 'ocr_extract_ga_antworten.py'), String(dokumentId), '--force-ocr'],
          { cwd: WORKSPACE_ROOT, timeout: 300_000, maxBuffer: 10 * 1024 * 1024 },
          (err, stdout, stderr) => {
            if (err) return reject(err);
            if (stderr) this.logger.log(`OCR stderr: ${stderr.substring(0, 500)}`);
            try { resolve(JSON.parse(stdout)); }
            catch { reject(new Error('OCR JSON parse error')); }
          },
        );
      });
      ocrText = ocrResult.full_text;
      this.logger.log(`OCR: ${ocrResult.total_chars} chars, ${ocrResult.page_count} pages, ocr_used=${ocrResult.ocr_used}`);
    }

    if (!ocrText || ocrText.length < 20) {
      throw new Error('OCR konnte keinen Text aus dem Dokument extrahieren. Ist die PDF leer oder beschädigt?');
    }

    // 3. Load Handreichung/Musterlösungen for context
    const musterloesungen = dokument.pruefung_id
      ? await this.prisma.musterloesungen.findMany({
          where: { pruefung_id: dokument.pruefung_id },
          orderBy: { aufgabe: 'asc' },
        })
      : [];

    const musterBlock = musterloesungen.length
      ? musterloesungen.map(m => `- ${m.aufgabe}: ${m.erwartung_text} (${m.max_punkte} Punkte)`).join('\n')
      : '(Keine Musterlösungen in der DB vorhanden)';

    // 3b. Load original Aufgabe PDF text for context (the exam questions)
    let aufgabenText = '';
    if (dokument.pruefung_id) {
      const aufgabeDok = await this.prisma.dokumente.findFirst({
        where: {
          pruefung_id: dokument.pruefung_id,
          typ: 'Aufgabe',
          pruefungsbereich: dokument.pruefungsbereich || undefined,
          id: { not: dokumentId }, // Don't use the bearbeitete doc itself
        },
      });
      if (aufgabeDok?.pfad) {
        try {
          const { readFileSync } = await import('fs');
          const pdfPath = join(WORKSPACE_ROOT, aufgabeDok.pfad);
          // Try to extract text via Python fitz
          const { execFileSync } = await import('child_process');
          const pyScript = `import fitz, sys, json
doc = fitz.open(sys.argv[1])
text = "\\n".join(p.get_text() for p in doc[:20])
doc.close()
print(json.dumps({"text": text[:20000]}))`;
          const pyResult = execFileSync(
            join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe'),
            ['-c', pyScript, pdfPath],
            { timeout: 30_000, maxBuffer: 5 * 1024 * 1024, cwd: WORKSPACE_ROOT },
          );
          const parsed = JSON.parse(pyResult.toString());
          aufgabenText = parsed.text || '';
          this.logger.log(`Aufgaben-PDF geladen: ${aufgabenText.length} chars von "${aufgabeDok.dateiname}"`);
        } catch (e) {
          this.logger.warn(`Aufgaben-PDF konnte nicht geladen werden: ${e.message}`);
        }
      }
    }

    // 3c. Load Handreichung/Lösung PDF text for context
    let handreichungText = '';
    if (dokument.pruefung_id) {
      const handreichungDok = await this.prisma.dokumente.findFirst({
        where: {
          pruefung_id: dokument.pruefung_id,
          typ: { in: ['Lösung', 'Handreichung'] },
          pruefungsbereich: dokument.pruefungsbereich || undefined,
        },
      });
      if (handreichungDok?.pfad) {
        try {
          const { execFileSync } = await import('child_process');
          const pdfPath = join(WORKSPACE_ROOT, handreichungDok.pfad);
          const pyScript = `import fitz, sys, json
doc = fitz.open(sys.argv[1])
text = "\\n".join(p.get_text() for p in doc[:20])
doc.close()
print(json.dumps({"text": text[:20000]}))`;
          const pyResult = execFileSync(
            join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe'),
            ['-c', pyScript, pdfPath],
            { timeout: 30_000, maxBuffer: 5 * 1024 * 1024, cwd: WORKSPACE_ROOT },
          );
          const parsed = JSON.parse(pyResult.toString());
          handreichungText = parsed.text || '';
          this.logger.log(`Handreichung/Lösung-PDF geladen: ${handreichungText.length} chars von "${handreichungDok.dateiname}"`);
        } catch (e) {
          this.logger.warn(`Handreichung-PDF konnte nicht geladen werden: ${e.message}`);
        }
      }
    }

    // 4. Build prompt
    const aufgabenBlock = aufgabenText
      ? `## Original-Prüfungsaufgaben (IHK-Aufgabenstellung):\n${aufgabenText.substring(0, 12000)}\n${aufgabenText.length > 12000 ? '[... Text gekürzt ...]' : ''}\n`
      : '';

    const handreichungBlock = handreichungText
      ? `## Musterlösung / Handreichung (erwartete Antworten):\n${handreichungText.substring(0, 12000)}\n${handreichungText.length > 12000 ? '[... Text gekürzt ...]' : ''}\n`
      : '';

    const prompt = `Du bist ein erfahrener IHK-Prüfungsanalysator für die Abschlussprüfung Teil 2 (FIAE - Fachinformatiker Anwendungsentwicklung).

## Prüfung: ${dokument.pruefung?.zeitraum_label || 'Unbekannt'}
## Prüfungsbereich: ${dokument.pruefungsbereich || 'GA1'}

## Deine Aufgabe:
Analysiere den folgenden OCR-Text einer **ausgefüllten Prüfung** (bearbeitete Version mit Antworten des Prüflings).
Extrahiere ALLE Aufgaben und die dazugehörigen Antworten des Prüflings.
Nutze die Original-Aufgabenstellung und ggf. die Musterlösung, um die Aufgabenstruktur und max. Punktzahlen korrekt zu identifizieren.

## Regeln:
1. Identifiziere jede Aufgabe anhand ihrer Nummerierung (z.B. "1a", "1b", "2a", "2b", "3", etc.)
2. Extrahiere die **ANTWORT des Prüflings** - NICHT den Aufgabentext
3. Bei Multiple-Choice: Nur die angekreuzte/markierte Option
4. Bei Freitext: Den vollständigen Antworttext
5. Bei Diagrammen/Zeichnungen: Beschreibe was erkennbar ist
6. Aufgabennamen im Format: "1a", "1b", "2a" etc. (Zahl + Buchstabe, ohne Leerzeichen)
7. Wenn eine Aufgabe nicht beantwortet wurde, setze antwort auf "(nicht beantwortet)"
8. Nutze die Punkteverteilung aus der Aufgabenstellung oder Musterlösung für max_punkte
9. Extrahiere auch die **Aufgabenstellung** (Fragetext) für jede Aufgabe im Feld "frage"

${aufgabenBlock}${handreichungBlock}${musterloesungen.length ? '## Bekannte Aufgabenstruktur (aus DB-Musterlösung):\n' + musterBlock + '\n' : ''}
## OCR-Text der ausgefüllten Prüfung (Antworten des Prüflings):
${ocrText.substring(0, 15000)}
${ocrText.length > 15000 ? '\n[... Text gekürzt ...]' : ''}

## Antwortformat:
Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein anderer Text!):
{
  "aufgaben": [
    {"aufgabe": "1a", "frage": "Die Original-Aufgabenstellung...", "antwort": "Die Antwort des Prüflings...", "max_punkte": 5},
    {"aufgabe": "1b", "frage": "...", "antwort": "...", "max_punkte": 10},
    ...
  ]
}`;

    // 5. Call LLM
    if (!model) {
      if (provider === 'perplexity') model = 'sonar-pro';
      else if (provider === 'ollama') model = 'llama3.2:3b';
      else model = 'gpt-4o-mini';
    }

    const start = Date.now();
    let result: LlmResponse;
    if (provider === 'ollama') {
      result = await this.callOllama(prompt, model);
    } else if (provider === 'perplexity') {
      result = await this.callPerplexity(prompt, model);
    } else {
      result = await this.callOpenAI(prompt, model);
    }
    const dauer = Date.now() - start;

    // 6. Parse response
    const details = result.details as any;
    let aufgaben: Array<{ aufgabe: string; antwort: string; max_punkte?: number }> = [];

    if (details?.aufgaben && Array.isArray(details.aufgaben)) {
      aufgaben = details.aufgaben;
    } else {
      // Try to find aufgaben array in the raw response
      const rawContent = JSON.stringify(details);
      const match = rawContent.match(/"aufgaben"\s*:\s*(\[[\s\S]*?\])/);
      if (match) {
        try {
          aufgaben = JSON.parse(match[1]);
        } catch {
          this.logger.warn('Could not parse aufgaben from LLM response');
        }
      }
    }

    return {
      aufgaben,
      provider,
      model: model!,
      dauer_ms: dauer,
      ocr_chars: ocrText.length,
    };
  }

  /** Grade all ungraded answers of a specific exam */
  async bewertenPruefung(
    pruefungId: number,
    provider: 'ollama' | 'openai' | 'perplexity',
    model?: string,
    durchlauf?: number,
  ) {
    // Falls kein Durchlauf angegeben, den höchsten ermitteln
    let dl = durchlauf;
    if (dl == null) {
      const latest = await this.prisma.antworten.findFirst({
        where: { pruefung_id: pruefungId, durchlauf: { gte: 1 }, aufgabe: { not: { startsWith: 'KEY_' } } },
        orderBy: { durchlauf: 'desc' },
        select: { durchlauf: true },
      });
      dl = latest?.durchlauf ?? 1;
    }

    const antworten = await this.prisma.antworten.findMany({
      where: {
        pruefung_id: pruefungId,
        durchlauf: dl,
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
        antwort: { pruefung_id: pruefungId },
      },
      include: {
        antwort: { select: { aufgabe: true, antwort_text: true } },
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

  /** Extract questions from an Aufgabe-PDF and save as musterloesungen */
  async extractFragenFromDokument(
    dokumentId: number,
    provider: 'ollama' | 'openai' | 'perplexity' = 'perplexity',
    model?: string,
  ): Promise<{
    extracted: number;
    skipped: number;
    aufgaben: Array<{ aufgabe: string; frage: string; max_punkte: number | null }>;
    provider: string;
    model: string;
    dauer_ms: number;
  }> {
    // 1. Get document info
    const dokument = await this.prisma.dokumente.findUnique({
      where: { id: dokumentId },
      include: { pruefung: true },
    });
    if (!dokument) throw new Error(`Dokument ${dokumentId} nicht gefunden`);
    if (!dokument.pruefung_id) throw new Error('Dokument hat keine zugeordnete Prüfung');

    // 2. Get OCR text from seiten table
    const seiten = await this.prisma.seiten.findMany({
      where: { dokument_id: dokumentId },
      orderBy: { seiten_nr: 'asc' },
      select: { ocr_text: true, seiten_nr: true },
    });

    let fullText = seiten
      .filter(s => s.ocr_text)
      .map(s => s.ocr_text)
      .join('\n\n');

    // 3. If no OCR text in DB, try to extract from PDF via fitz
    if (!fullText || fullText.length < 50) {
      if (dokument.pfad) {
        try {
          const pdfPath = join(WORKSPACE_ROOT, dokument.pfad);
          const { execFileSync } = await import('child_process');
          const pyScript = `import fitz, sys, json
doc = fitz.open(sys.argv[1])
text = "\\n\\n".join(f"--- Seite {i+1} ---\\n" + p.get_text() for i, p in enumerate(doc[:30]))
doc.close()
print(json.dumps({"text": text[:30000]}))`;
          const pyResult = execFileSync(
            join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe'),
            ['-c', pyScript, pdfPath],
            { timeout: 30_000, maxBuffer: 5 * 1024 * 1024, cwd: WORKSPACE_ROOT },
          );
          const parsed = JSON.parse(pyResult.toString());
          fullText = parsed.text || '';
          this.logger.log(`Fragen-Extraktion: PDF-Text via fitz geladen: ${fullText.length} chars`);
        } catch (e) {
          this.logger.warn(`PDF-Text konnte nicht geladen werden: ${e.message}`);
        }
      }
    }

    if (!fullText || fullText.length < 50) {
      throw new Error('Kein Text im Dokument gefunden. Bitte zuerst OCR durchführen.');
    }

    // 4. Determine bereich prefix from document
    const bereich = dokument.pruefungsbereich || '';
    let aufgabePrefix = '';
    if (bereich === 'GA2') aufgabePrefix = 'GA2_';
    // WISO numbers stay as-is (1-30)

    // 5. Build LLM prompt for question extraction
    const isWiso = bereich === 'WISO' || dokument.dateiname?.toLowerCase().includes('wiso');

    let prompt: string;
    if (isWiso) {
      prompt = `Du bist ein erfahrener IHK-Prüfungsanalysator für die Abschlussprüfung Teil 2 (FIAE - Fachinformatiker Anwendungsentwicklung).

## Prüfung: ${dokument.pruefung?.zeitraum_label || 'Unbekannt'}
## Prüfungsbereich: WISO (Wirtschafts- und Sozialkunde)

## Deine Aufgabe:
Analysiere den folgenden Text einer WISO-Prüfungsaufgabe und extrahiere ALLE Fragen.
WISO-Prüfungen bestehen typischerweise aus ca. 30 Multiple-Choice-Aufgaben.

## Regeln:
1. Jede Aufgabe hat eine Nummer (1-30)
2. Extrahiere den vollständigen Fragetext inklusive aller Antwortmöglichkeiten
3. max_punkte ist typischerweise 1 pro Aufgabe (oder wie angegeben)

## Text der Prüfungsaufgabe:
${fullText.substring(0, 20000)}
${fullText.length > 20000 ? '\n[... Text gekürzt ...]' : ''}

## Antwortformat:
Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein anderer Text!):
{
  "aufgaben": [
    {"aufgabe": "1", "frage": "Der vollständige Fragetext mit allen Antwortmöglichkeiten...", "max_punkte": 1},
    {"aufgabe": "2", "frage": "...", "max_punkte": 1},
    ...
  ]
}`;
    } else {
      prompt = `Du bist ein erfahrener IHK-Prüfungsanalysator für die Abschlussprüfung Teil 2 (FIAE - Fachinformatiker Anwendungsentwicklung).

## Prüfung: ${dokument.pruefung?.zeitraum_label || 'Unbekannt'}
## Prüfungsbereich: ${bereich || 'GA1'}

## Deine Aufgabe:
Analysiere den folgenden Text einer Prüfungsaufgabe und extrahiere ALLE Aufgabenstellungen (Fragen).
Extrahiere NUR die Fragestellungen, NICHT die Antworten.

## Regeln:
1. Identifiziere jede Aufgabe anhand ihrer Nummerierung (z.B. "1a", "1b", "2a", "2b", "3", etc.)
2. Extrahiere den vollständigen Aufgabentext/Fragetext
3. Beachte die Punkteverteilung (oft in Klammern: "(10 Punkte)" oder ähnlich)
4. Aufgabennamen im Format: "1a", "1b", "2a" etc. (Zahl + Buchstabe, ohne Leerzeichen)
5. Bei Unteraufgaben wie "3a)" innerhalb von Aufgabe 3 verwende "3a"
6. Bei doppelt verschachtelten Aufgaben wie Aufgabe 3, Teil a, Unterpunkt i → verwende "3ai"
7. Gib auch Kontext zur Aufgabe mit (z.B. Ausgangssituation, die für mehrere Unteraufgaben gilt)
8. Wenn eine Ausgangssituation für mehrere Aufgaben gilt, füge sie als Kontext bei jeder betroffenen Aufgabe hinzu

## Text der Prüfungsaufgabe:
${fullText.substring(0, 20000)}
${fullText.length > 20000 ? '\n[... Text gekürzt ...]' : ''}

## Antwortformat:
Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein anderer Text!):
{
  "aufgaben": [
    {"aufgabe": "1a", "frage": "Die vollständige Aufgabenstellung inkl. Kontext...", "max_punkte": 10},
    {"aufgabe": "1b", "frage": "...", "max_punkte": 5},
    ...
  ]
}`;
    }

    // 6. Call LLM
    if (!model) {
      if (provider === 'perplexity') model = 'sonar-pro';
      else if (provider === 'ollama') model = 'llama3.2:3b';
      else model = 'gpt-4o-mini';
    }

    const start = Date.now();
    let result: LlmResponse;
    if (provider === 'ollama') {
      result = await this.callOllama(prompt, model);
    } else if (provider === 'perplexity') {
      result = await this.callPerplexity(prompt, model);
    } else {
      result = await this.callOpenAI(prompt, model);
    }
    const dauer = Date.now() - start;

    // 7. Parse response
    const details = result.details as any;
    let aufgaben: Array<{ aufgabe: string; frage: string; max_punkte?: number }> = [];

    if (details?.aufgaben && Array.isArray(details.aufgaben)) {
      aufgaben = details.aufgaben;
    } else {
      const rawContent = JSON.stringify(details);
      const match = rawContent.match(/"aufgaben"\s*:\s*(\[[\s\S]*?\])/);
      if (match) {
        try { aufgaben = JSON.parse(match[1]); } catch { /* ignore */ }
      }
    }

    if (!aufgaben.length) {
      throw new Error('KI konnte keine Aufgaben aus dem Text extrahieren');
    }

    // 8. Save to musterloesungen (upsert to avoid duplicates)
    let extracted = 0;
    let skipped = 0;
    const savedAufgaben: Array<{ aufgabe: string; frage: string; max_punkte: number | null }> = [];

    for (const a of aufgaben) {
      const aufgabeName = aufgabePrefix + a.aufgabe.trim();
      const frage = a.frage?.trim() || '';
      if (!aufgabeName || !frage) { skipped++; continue; }

      try {
        await this.prisma.musterloesungen.upsert({
          where: {
            pruefung_id_aufgabe: {
              pruefung_id: dokument.pruefung_id!,
              aufgabe: aufgabeName,
            },
          },
          create: {
            pruefung_id: dokument.pruefung_id!,
            aufgabe: aufgabeName,
            erwartung_text: '',
            max_punkte: a.max_punkte || null,
            hinweise: frage,
          },
          update: {
            hinweise: frage,
            max_punkte: a.max_punkte || undefined,
          },
        });
        extracted++;
        savedAufgaben.push({ aufgabe: aufgabeName, frage, max_punkte: a.max_punkte || null });
      } catch (e) {
        this.logger.warn(`Musterloesungen upsert failed for ${aufgabeName}: ${e.message}`);
        skipped++;
      }
    }

    this.logger.log(`Fragen-Extraktion: ${extracted} extrahiert, ${skipped} übersprungen, Bereich=${bereich}, Prefix=${aufgabePrefix}`);

    return {
      extracted,
      skipped,
      aufgaben: savedAufgaben,
      provider,
      model: model!,
      dauer_ms: dauer,
    };
  }

  /** Extract solutions from a Lösung/Handreichung PDF and update musterloesungen.erwartung_text */
  async extractLoesungenFromDokument(
    dokumentId: number,
    provider: 'ollama' | 'openai' | 'perplexity' = 'perplexity',
    model?: string,
  ): Promise<{
    updated: number;
    created: number;
    skipped: number;
    aufgaben: Array<{ aufgabe: string; loesung: string; max_punkte: number | null }>;
    provider: string;
    model: string;
    dauer_ms: number;
  }> {
    // 1. Get document info
    const dokument = await this.prisma.dokumente.findUnique({
      where: { id: dokumentId },
      include: { pruefung: true },
    });
    if (!dokument) throw new Error(`Dokument ${dokumentId} nicht gefunden`);
    if (!dokument.pruefung_id) throw new Error('Dokument hat keine zugeordnete Prüfung');

    // 2. Get OCR text from seiten table
    const seiten = await this.prisma.seiten.findMany({
      where: { dokument_id: dokumentId },
      orderBy: { seiten_nr: 'asc' },
      select: { ocr_text: true, seiten_nr: true },
    });

    let fullText = seiten
      .filter(s => s.ocr_text)
      .map(s => s.ocr_text)
      .join('\n\n');

    // 3. If no OCR text in DB, try to extract from PDF via fitz
    if (!fullText || fullText.length < 50) {
      if (dokument.pfad) {
        try {
          const pdfPath = join(WORKSPACE_ROOT, dokument.pfad);
          if (!existsSync(pdfPath)) {
            throw new Error(`PDF-Datei nicht gefunden: ${pdfPath}`);
          }
          const { execFileSync } = await import('child_process');
          const pyScript = `import fitz, sys, json
doc = fitz.open(sys.argv[1])
text = "\\n\\n".join(f"--- Seite {i+1} ---\\n" + p.get_text() for i, p in enumerate(doc[:40]))
doc.close()
print(json.dumps({"text": text[:40000]}))`;
          const pyResult = execFileSync(
            join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe'),
            ['-c', pyScript, pdfPath],
            { timeout: 30_000, maxBuffer: 5 * 1024 * 1024, cwd: WORKSPACE_ROOT },
          );
          const parsed = JSON.parse(pyResult.toString());
          fullText = parsed.text || '';
          this.logger.log(`Lösungs-Extraktion: PDF-Text via fitz geladen: ${fullText.length} chars`);
        } catch (e) {
          this.logger.warn(`PDF-Text konnte nicht geladen werden: ${e.message}`);
        }
      }
    }

    if (!fullText || fullText.length < 50) {
      throw new Error('Kein Text im Lösungs-Dokument gefunden. Bitte zuerst OCR durchführen oder die PDF-Datei bereitstellen.');
    }

    // 4. Load existing musterloesungen for context (so LLM knows the aufgabe names)
    const existingMuster = await this.prisma.musterloesungen.findMany({
      where: { pruefung_id: dokument.pruefung_id! },
      orderBy: { aufgabe: 'asc' },
    });

    const bereich = dokument.pruefungsbereich || '';
    let aufgabePrefix = '';
    if (bereich === 'GA2') aufgabePrefix = 'GA2_';

    // Filter musterloesungen to the relevant bereich
    const relevantMuster = existingMuster.filter(m => {
      if (bereich === 'GA2') return m.aufgabe.startsWith('GA2_');
      if (bereich === 'WISO') return /^\d+(\.\d+)?$/.test(m.aufgabe);
      // GA1: not GA2_ and not pure number
      return !m.aufgabe.startsWith('GA2_') && !/^\d+$/.test(m.aufgabe);
    });

    const musterContext = relevantMuster.length
      ? '\n## Bekannte Aufgaben (aus DB):\n' + relevantMuster.map(m =>
        `- ${m.aufgabe}: ${m.hinweise ? m.hinweise.substring(0, 100) : '(keine Fragestellung)'} [${m.max_punkte || '?'} Punkte]`
      ).join('\n') + '\n'
      : '';

    // 5. Build LLM prompt
    const isWiso = bereich === 'WISO' || dokument.dateiname?.toLowerCase().includes('wiso');

    const prompt = `Du bist ein erfahrener IHK-Prüfungsanalysator für die Abschlussprüfung Teil 2 (FIAE - Fachinformatiker Anwendungsentwicklung).

## Prüfung: ${dokument.pruefung?.zeitraum_label || 'Unbekannt'}
## Prüfungsbereich: ${bereich || 'GA1'}
## Dokumenttyp: Lösung / Handreichung / Erwartungshorizont

## Deine Aufgabe:
Analysiere den folgenden Text einer **Musterlösung/Handreichung** und extrahiere die **erwarteten Lösungen** für jede Aufgabe.
${isWiso ? 'Bei WISO-Aufgaben: Extrahiere die richtige Antwort-Nummer oder den Lösungstext.' : 'Extrahiere den vollständigen Erwartungshorizont / die Musterlösung für jede Aufgabe.'}

## Regeln:
1. Identifiziere jede Aufgabe anhand ihrer Nummerierung (z.B. "1a", "1b", "2a", etc.)
2. Extrahiere die **MUSTERLÖSUNG / erwartete Antwort** – NICHT den Aufgabentext
3. Bei Handreichungen: Extrahiere den Erwartungshorizont (was der Prüfling schreiben soll)
4. Aufgabennamen im Format: "1a", "1b", "2a" etc. (Zahl + Buchstabe, ohne Leerzeichen)
5. Wenn Punkte pro Kriterium/Aspekt angegeben sind, extrahiere auch die Punkteverteilung
6. Gib die vollständige Lösung mit allen erwarteten Aspekten an
7. Bei SQL-Aufgaben: Gib die SQL-Abfrage als Lösung an
8. Bei Pseudocode: Gib den erwarteten Pseudocode an
9. Bei Diagrammen: Beschreibe die erwarteten Elemente und Beziehungen
${musterContext}
## Text der Musterlösung/Handreichung:
${fullText.substring(0, 20000)}
${fullText.length > 20000 ? '\n[... Text gekürzt ...]' : ''}

## Antwortformat:
Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein anderer Text!):
{
  "aufgaben": [
    {"aufgabe": "1a", "loesung": "Die vollständige Musterlösung/erwartete Antwort...", "max_punkte": 10},
    {"aufgabe": "1b", "loesung": "...", "max_punkte": 5},
    ...
  ]
}`;

    // 6. Call LLM
    if (!model) {
      if (provider === 'perplexity') model = 'sonar-pro';
      else if (provider === 'ollama') model = 'llama3.2:3b';
      else model = 'gpt-4o-mini';
    }

    const start = Date.now();
    let result: LlmResponse;
    if (provider === 'ollama') {
      result = await this.callOllama(prompt, model);
    } else if (provider === 'perplexity') {
      result = await this.callPerplexity(prompt, model);
    } else {
      result = await this.callOpenAI(prompt, model);
    }
    const dauer = Date.now() - start;

    // 7. Parse response
    const details = result.details as any;
    let aufgaben: Array<{ aufgabe: string; loesung: string; max_punkte?: number }> = [];

    if (details?.aufgaben && Array.isArray(details.aufgaben)) {
      aufgaben = details.aufgaben;
    } else {
      const rawContent = JSON.stringify(details);
      const match = rawContent.match(/"aufgaben"\s*:\s*(\[[\s\S]*?\])/);
      if (match) {
        try { aufgaben = JSON.parse(match[1]); } catch { /* ignore */ }
      }
    }

    if (!aufgaben.length) {
      throw new Error('KI konnte keine Lösungen aus dem Text extrahieren');
    }

    // 8. Save to musterloesungen (upsert)
    let updated = 0;
    let created = 0;
    let skipped = 0;
    const savedAufgaben: Array<{ aufgabe: string; loesung: string; max_punkte: number | null }> = [];

    for (const a of aufgaben) {
      const aufgabeName = aufgabePrefix + a.aufgabe.trim();
      const loesung = a.loesung?.trim() || '';
      if (!aufgabeName || !loesung) { skipped++; continue; }

      try {
        // Check if musterloesungen exists for this aufgabe
        const existing = await this.prisma.musterloesungen.findUnique({
          where: {
            pruefung_id_aufgabe: {
              pruefung_id: dokument.pruefung_id!,
              aufgabe: aufgabeName,
            },
          },
        });

        if (existing) {
          // Update erwartung_text
          await this.prisma.musterloesungen.update({
            where: { id: existing.id },
            data: {
              erwartung_text: loesung,
              max_punkte: a.max_punkte || existing.max_punkte || undefined,
            },
          });
          updated++;
        } else {
          // Create new musterloesungen entry
          await this.prisma.musterloesungen.create({
            data: {
              pruefung_id: dokument.pruefung_id!,
              aufgabe: aufgabeName,
              erwartung_text: loesung,
              max_punkte: a.max_punkte || null,
              hinweise: '', // No question text from Lösung PDF
            },
          });
          created++;
        }
        savedAufgaben.push({ aufgabe: aufgabeName, loesung, max_punkte: a.max_punkte || null });
      } catch (e) {
        this.logger.warn(`Musterloesungen upsert (Lösung) failed for ${aufgabeName}: ${e.message}`);
        skipped++;
      }
    }

    this.logger.log(`Lösungs-Extraktion: ${updated} aktualisiert, ${created} neu erstellt, ${skipped} übersprungen, Bereich=${bereich}`);

    return {
      updated,
      created,
      skipped,
      aufgaben: savedAufgaben,
      provider,
      model: model!,
      dauer_ms: dauer,
    };
  }

  /** Check LLM provider availability */
  async checkProvider(provider: 'ollama' | 'openai' | 'perplexity'): Promise<{
    available: boolean;
    models?: string[];
    error?: string;
  }> {
    if (provider === 'ollama') {
      return this.checkOllama();
    }
    if (provider === 'perplexity') {
      return this.checkPerplexity();
    }
    return this.checkOpenAI();
  }

  /** Start Ollama Docker container */
  async startOllama(): Promise<{ success: boolean; message: string }> {
    try {
      // Check if container exists
      const ps = execSync('docker ps -a --filter name=ollama --format "{{.Status}}"', {
        encoding: 'utf-8',
        timeout: 10000,
      }).trim();

      if (!ps) {
        // Container doesn't exist → create and run
        this.logger.log('Ollama container not found, creating...');
        execSync(
          'docker run -d --name ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama',
          { encoding: 'utf-8', timeout: 30000 },
        );
        // Wait for the API to become available
        await this.waitForOllama(15);
        // Pull default model if not present
        try {
          execSync('docker exec ollama ollama pull llama3.2:3b', {
            encoding: 'utf-8',
            timeout: 300000, // 5 min for model pull
          });
        } catch {
          this.logger.warn('Model pull may have failed, continuing...');
        }
        return { success: true, message: 'Ollama Container erstellt und gestartet' };
      }

      if (ps.startsWith('Up')) {
        return { success: true, message: 'Ollama läuft bereits' };
      }

      // Container exists but is stopped → start it
      this.logger.log('Starting stopped Ollama container...');
      execSync('docker start ollama', { encoding: 'utf-8', timeout: 15000 });
      await this.waitForOllama(10);
      return { success: true, message: 'Ollama Container gestartet' };
    } catch (e) {
      this.logger.error('Failed to start Ollama:', e);
      return { success: false, message: `Fehler beim Starten: ${e.message || e}` };
    }
  }

  /** Stop Ollama Docker container */
  async stopOllama(): Promise<{ success: boolean; message: string }> {
    try {
      execSync('docker stop ollama', { encoding: 'utf-8', timeout: 15000 });
      return { success: true, message: 'Ollama Container gestoppt' };
    } catch (e) {
      return { success: false, message: `Fehler beim Stoppen: ${e.message || e}` };
    }
  }

  /** Wait for Ollama API to respond */
  private async waitForOllama(maxRetries = 10): Promise<void> {
    const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434';
    for (let i = 0; i < maxRetries; i++) {
      try {
        const resp = await fetch(ollamaUrl, { signal: AbortSignal.timeout(2000) });
        if (resp.ok) return;
      } catch {
        // not ready yet
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  /* ═══════════════ PROMPT BUILDING ═══════════════ */

  private buildPrompt(
    aufgabe: string,
    antwort: string,
    musterloesung: string | null,
    maxPunkte: number,
    pruefung: string,
    hasImages = false,
  ): string {
    const musterBlock = musterloesung
      ? `\n## Musterlösung / Erwartungshorizont:\n${musterloesung}\n`
      : '\n(Keine Musterlösung verfügbar - bewerte nach fachlicher Korrektheit)\n';

    const imageHint = hasImages
      ? `\n**WICHTIG:** Der Prüfling hat seine Antwort handschriftlich bzw. als Bild/Scan/Diagramm eingereicht. Analysiere die beigefügten Bilder sorgfältig. Bei Diagrammen (UML, Sequenz, ER, Klassen etc.) bewerte Korrektheit der Notation, Vollständigkeit und fachliche Richtigkeit.\n`
      : '';

    return `Du bist ein erfahrener, wohlwollender IHK-Prüfer für die Abschlussprüfung Teil 2 (FIAE - Fachinformatiker Anwendungsentwicklung).
Du bewertest gemäß den offiziellen IHK-Richtlinien und dem IHK-Bewertungsschlüssel.

## Prüfung: ${pruefung}
## Aufgabe: ${aufgabe}
## Maximale Punktzahl: ${maxPunkte}
${musterBlock}${imageHint}
## Antwort des Prüflings:
${antwort}

## IHK-konforme Bewertungsregeln:
Bewerte die Antwort nach den folgenden IHK-Grundsätzen:

1. **Wohlwollensprinzip (§ 25 BBiG)**: Bewerte im Zweifel ZUGUNSTEN des Prüflings. Wenn eine Antwort fachlich vertretbar ist, auch wenn sie von der Musterlösung abweicht, vergib Punkte.
2. **Inhaltliche Korrektheit**: Stimmen die Kernaussagen überein? Synonyme, Umformulierungen und alternative Fachbegriffe sind GLEICHWERTIG, solange der fachliche Inhalt korrekt ist.
3. **Musterlösung ist ein Richtwert, kein Pflichttext**: Die Musterlösung dient als Orientierung. Andere Lösungswege und Formulierungen sind ebenso gültig, wenn sie fachlich korrekt sind.
4. **Vollständigkeit**: Wurden die wesentlichen Aspekte genannt? Nicht erwähnte Randaspekte führen nicht automatisch zum Punktabzug.
5. **Fachliche Tiefe**: Zeigt der Prüfling grundlegendes Verständnis des Themas?
6. **Teilpunkte**: Vergib großzügig Teilpunkte für teilweise richtige Antworten. Jeder korrekte Aspekt zählt.
7. **Praxisbezug**: Praxisnahe Antworten, die über die Musterlösung hinausgehen, sind positiv zu bewerten.
8. **Formale Fehler**: Rechtschreib- oder Grammatikfehler führen NICHT zu Punktabzug, solange der Inhalt verständlich ist.

## Lösungsvorschlag bei Punktabzug:
Falls der Prüfling NICHT die volle Punktzahl erreicht, erstelle einen Lösungsvorschlag:
- Formuliere die Antwort so, wie ein Prüfling sie in der IHK-Prüfung schreiben würde (prägnant, fachlich korrekt, prüfungstauglich)
- Orientiere dich an der Musterlösung, aber formuliere in natürlicher Prüflings-Sprache
- Erkläre kurz, WARUM diese Antwort die volle Punktzahl verdient
- Berücksichtige das IHK-Niveau: Die Antwort soll einem Fachinformatiker-Azubi entsprechen, nicht einem Informatik-Professor

WICHTIG: Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein anderer Text!):
{
  "punkte": <number zwischen 0 und ${maxPunkte}>,
  "max_punkte": ${maxPunkte},
  "feedback": "<kurze deutschsprachige Begründung der Bewertung aus Prüfersicht, max 3 Sätze. Erkläre was gut war und was gefehlt hat.>",
  "korrekte_aspekte": ["<was richtig war>"],
  "fehlende_aspekte": ["<was gefehlt hat oder verbessert werden könnte>"],
  "loesungsvorschlag": "<Falls punkte < max_punkte: Eine IHK-konforme Musterantwort aus Prüflingssicht, die die volle Punktzahl erreichen würde, mit kurzer Erklärung warum. Falls volle Punktzahl: null>",
  "konfidenz": <0.0-1.0 wie sicher du dir bei der Bewertung bist>
}`;
  }

  /* ═══════════════ OLLAMA ═══════════════ */

  private async callOllama(
    prompt: string,
    model: string,
    images?: string[],
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

    // Vision: add images if present
    if (images?.length) {
      body.images = images;
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
    images?: string[],
  ): Promise<LlmResponse> {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) throw new Error('OPENAI_API_KEY nicht gesetzt (in .env)');

    const messages: Array<Record<string, unknown>> = [];

    if (images?.length) {
      // Vision request with multiple images
      const content: Array<Record<string, unknown>> = [
        { type: 'text', text: prompt },
      ];
      for (const img of images) {
        content.push({
          type: 'image_url',
          image_url: { url: `data:image/png;base64,${img}`, detail: 'high' },
        });
      }
      messages.push({ role: 'user', content });
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

  /* ═══════════════ PERPLEXITY ═══════════════ */

  private async callPerplexity(
    prompt: string,
    model: string,
  ): Promise<LlmResponse> {
    const apiKey = process.env.PERPLEXITY_API_KEY;
    if (!apiKey) throw new Error('PERPLEXITY_API_KEY nicht gesetzt (in .env)');

    const messages: Array<Record<string, unknown>> = [
      { role: 'user', content: prompt },
    ];

    const resp = await fetch('https://api.perplexity.ai/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.1,
        max_tokens: 4096,
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`Perplexity error: ${resp.status} ${errText}`);
    }

    const data = (await resp.json()) as {
      choices: Array<{ message: { content: string } }>;
      usage?: { prompt_tokens: number; completion_tokens: number };
    };

    const content = data.choices[0]?.message?.content || '{}';
    this.logger.log(`Perplexity raw (first 500): ${content.substring(0, 500)}`);
    this.logger.log(`Perplexity len=${content.length}, tokens=${data.usage?.completion_tokens}`);
    const parsed = this.parseJsonResponse(content);

    return {
      punkte: parsed.punkte,
      max_punkte: parsed.max_punkte,
      feedback: parsed.feedback,
      details: parsed,
      provider: 'perplexity',
      model,
      prompt_tokens: data.usage?.prompt_tokens,
      completion_tokens: data.usage?.completion_tokens,
      dauer_ms: 0,
    };
  }

  private async checkPerplexity(): Promise<{
    available: boolean;
    models?: string[];
    error?: string;
  }> {
    const apiKey = process.env.PERPLEXITY_API_KEY;
    if (!apiKey) {
      return { available: false, error: 'PERPLEXITY_API_KEY nicht in .env gesetzt' };
    }
    try {
      // Perplexity has no /models endpoint – do a lightweight test call
      const resp = await fetch('https://api.perplexity.ai/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: 'sonar',
          messages: [{ role: 'user', content: 'ping' }],
          max_tokens: 1,
        }),
        signal: AbortSignal.timeout(10000),
      });
      if (resp.status === 401) {
        return { available: false, error: 'PERPLEXITY_API_KEY ist ungültig (401 Unauthorized). Prüfe den Key auf https://www.perplexity.ai/account/api' };
      }
      if (!resp.ok) throw new Error(`Status ${resp.status}`);
      return {
        available: true,
        models: ['sonar', 'sonar-pro', 'sonar-reasoning', 'sonar-reasoning-pro'],
      };
    } catch (e) {
      return { available: false, error: `Perplexity nicht erreichbar: ${e}` };
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

    // Remove Perplexity citation references like [1], [2] inside strings
    cleaned = cleaned.replace(/\[(\d+)\]/g, '');

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
      // Try to repair truncated JSON (e.g. from max_tokens cutoff)
      try {
        let truncated = cleaned.substring(start);
        // Close any open strings
        const quoteCount = (truncated.match(/(?<!\\)"/g) || []).length;
        if (quoteCount % 2 !== 0) truncated += '"';
        // Close arrays and objects
        const openBrackets = (truncated.match(/\[/g) || []).length - (truncated.match(/\]/g) || []).length;
        const openBraces = (truncated.match(/\{/g) || []).length - (truncated.match(/\}/g) || []).length;
        for (let i = 0; i < openBrackets; i++) truncated += ']';
        for (let i = 0; i < openBraces; i++) truncated += '}';
        // Remove trailing comma before closing brackets/braces
        truncated = truncated.replace(/,\s*([\]\}])/g, '$1');
        const repaired = JSON.parse(truncated);
        this.logger.log('Repaired truncated JSON successfully');
        return {
          punkte: Number(repaired.punkte) || 0,
          max_punkte: Number(repaired.max_punkte) || 0,
          feedback: String(repaired.feedback || ''),
          ...repaired,
        };
      } catch (e2) {
        this.logger.warn(`JSON repair also failed: ${e2}`);
        return {
          punkte: 0,
          max_punkte: 0,
          feedback: 'JSON-Parse-Fehler: ' + text.substring(0, 200),
        };
      }
    }
  }
}

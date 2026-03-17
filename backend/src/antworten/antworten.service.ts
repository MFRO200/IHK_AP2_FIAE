import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateAntwortDto, UpdateAntwortDto } from './dto/antworten.dto';

@Injectable()
export class AntwortenService {
  constructor(private readonly prisma: PrismaService) {}

  /** Alle Antworten einer Prüfung (optional nach Durchlauf filtern) */
  findByPruefung(pruefungId: number, durchlauf?: number) {
    return this.prisma.antworten.findMany({
      where: { pruefung_id: pruefungId, ...(durchlauf != null ? { durchlauf } : {}) },
      orderBy: { aufgabe: 'asc' },
      include: { bilder: { orderBy: { sortierung: 'asc' } } },
    });
  }

  /** Einzelne Antwort */
  findOne(id: number) {
    return this.prisma.antworten.findUniqueOrThrow({
      where: { id },
      include: { pruefung: true },
    });
  }

  /** Antwort anlegen oder aktualisieren (upsert by pruefung_id + aufgabe + durchlauf) */
  upsert(dto: CreateAntwortDto) {
    const dl = dto.durchlauf ?? 1;
    return this.prisma.antworten.upsert({
      where: {
        pruefung_id_aufgabe_durchlauf: {
          pruefung_id: dto.pruefung_id,
          aufgabe: dto.aufgabe,
          durchlauf: dl,
        },
      },
      create: {
        pruefung_id: dto.pruefung_id,
        aufgabe: dto.aufgabe,
        antwort_text: dto.antwort_text,
        notiz: dto.notiz,
        punkte: dto.punkte,
        max_punkte: dto.max_punkte,
        durchlauf: dl,
        dauer_sekunden: dto.dauer_sekunden,
      },
      update: {
        antwort_text: dto.antwort_text,
        notiz: dto.notiz,
        punkte: dto.punkte,
        max_punkte: dto.max_punkte,
        dauer_sekunden: dto.dauer_sekunden,
      },
    });
  }

  /** Antwort aktualisieren */
  update(id: number, dto: UpdateAntwortDto) {
    return this.prisma.antworten.update({
      where: { id },
      data: dto,
    });
  }

  /** Antwort löschen */
  remove(id: number) {
    return this.prisma.antworten.delete({ where: { id } });
  }

  /* ═══════════════ Bilder ═══════════════ */

  /** Alle Bilder einer Antwort */
  findBilder(antwortId: number) {
    return this.prisma.antwort_bilder.findMany({
      where: { antwort_id: antwortId },
      orderBy: { sortierung: 'asc' },
    });
  }

  /** Einzelnes Bild */
  findBild(bildId: number) {
    return this.prisma.antwort_bilder.findUnique({ where: { id: bildId } });
  }

  /** Bild anlegen */
  createBild(data: {
    antwort_id: number;
    dateiname: string;
    storage_pfad: string;
    dateigroesse: number;
  }) {
    return this.prisma.antwort_bilder.create({ data });
  }

  /** Bild löschen */
  removeBild(bildId: number) {
    return this.prisma.antwort_bilder.delete({ where: { id: bildId } });
  }

  /** Alle Bilder aller Antworten – gruppiert nach Prüfung+Aufgabe */
  async alleBilder() {
    const bilder = await this.prisma.antwort_bilder.findMany({
      orderBy: { erstellt_am: 'desc' },
      include: {
        antwort: {
          select: {
            id: true,
            pruefung_id: true,
            aufgabe: true,
            antwort_text: true,
            durchlauf: true,
            punkte: true,
            max_punkte: true,
            updated_am: true,
            pruefung: {
              select: { id: true, zeitraum_label: true },
            },
          },
        },
      },
    });
    return bilder.map((b) => ({
      id: b.id,
      antwort_id: b.antwort_id,
      dateiname: b.dateiname,
      storage_pfad: b.storage_pfad,
      dateigroesse: b.dateigroesse,
      sortierung: b.sortierung,
      erstellt_am: b.erstellt_am,
      aufgabe: b.antwort.aufgabe,
      durchlauf: b.antwort.durchlauf,
      antwort_text: b.antwort.antwort_text,
      punkte: b.antwort.punkte,
      max_punkte: b.antwort.max_punkte,
      pruefung_id: b.antwort.pruefung_id,
      zeitraum_label: b.antwort.pruefung.zeitraum_label,
    }));
  }

  /** Statistik: Wie viele Prüfungen haben Antworten? */
  async stats() {
    const result = await this.prisma.$queryRaw<
      Array<{ pruefung_id: number; zeitraum_label: string; aufgaben: bigint; mit_punkte: bigint; summe_punkte: number; summe_max: number }>
    >`
      SELECT a.pruefung_id,
             p.zeitraum_label,
             COUNT(*)                              AS aufgaben,
             COUNT(a.punkte)                       AS mit_punkte,
             COALESCE(SUM(a.punkte), 0)::float     AS summe_punkte,
             COALESCE(SUM(a.max_punkte), 0)::float AS summe_max
      FROM antworten a
      JOIN pruefungen p ON a.pruefung_id = p.id
      WHERE a.durchlauf = 1
      GROUP BY a.pruefung_id, p.zeitraum_label
      ORDER BY p.zeitraum_label
    `;
    return result.map((r) => ({
      pruefung_id: r.pruefung_id,
      zeitraum_label: r.zeitraum_label,
      aufgaben: Number(r.aufgaben),
      mit_punkte: Number(r.mit_punkte),
      summe_punkte: r.summe_punkte,
      summe_max: r.summe_max,
    }));
  }

  /** Alle Durchläufe einer Prüfung mit Statistiken */
  async durchlaeufe(pruefungId: number) {
    const result = await this.prisma.$queryRaw<
      Array<{
        durchlauf: number; aufgaben: bigint; richtig: bigint; falsch: bigint; offen: bigint;
        summe_punkte: number; summe_max: number; dauer: number | null; datum: Date;
      }>
    >`
      SELECT a.durchlauf,
             COUNT(*)                                              AS aufgaben,
             COUNT(CASE WHEN a.punkte > 0 THEN 1 END)             AS richtig,
             COUNT(CASE WHEN a.punkte = 0 THEN 1 END)             AS falsch,
             COUNT(CASE WHEN a.punkte IS NULL THEN 1 END)          AS offen,
             COALESCE(SUM(a.punkte), 0)::float                     AS summe_punkte,
             COALESCE(SUM(a.max_punkte), 0)::float                 AS summe_max,
             MAX(a.dauer_sekunden)                                 AS dauer,
             MAX(a.updated_am)                                     AS datum
      FROM antworten a
      WHERE a.pruefung_id = ${pruefungId}
        AND a.aufgabe NOT LIKE '%.%'
      GROUP BY a.durchlauf
      ORDER BY a.durchlauf
    `;
    return result.map((r) => ({
      durchlauf: r.durchlauf,
      aufgaben: Number(r.aufgaben),
      richtig: Number(r.richtig),
      falsch: Number(r.falsch),
      offen: Number(r.offen),
      summe_punkte: r.summe_punkte,
      summe_max: r.summe_max,
      dauer_sekunden: r.dauer,
      datum: r.datum,
    }));
  }

  /** Bearbeitungsstatus: Welche Prüfung + Prüfungsbereich wurden geübt?
   *  Erkennung über:
   *  1. Explizite BEREICH_-Marker (durchlauf=0)
   *  2. Fallback: Prüfungen mit Antworten (bewertete ODER unbewertete)
   */
  async bearbeitungsStatus() {
    const result = await this.prisma.$queryRaw<
      Array<{
        pruefung_id: number;
        pruefungsbereich: string;
        durchlaeufe: bigint;
        ausgewertet: boolean;
        letzte_bearbeitung: Date;
      }>
    >`
      WITH marker AS (
        -- Explizite BEREICH-Marker
        SELECT pruefung_id,
               REPLACE(aufgabe, 'BEREICH_', '') AS pruefungsbereich,
               updated_am
        FROM antworten
        WHERE durchlauf = 0
          AND aufgabe LIKE 'BEREICH_%'
      ),
      answered AS (
        -- Prüfungen mit Antworten (bewertet oder unbewertet)
        SELECT pruefung_id,
               COUNT(DISTINCT durchlauf) AS durchlaeufe,
               BOOL_OR(punkte IS NOT NULL) AS ausgewertet,
               MAX(updated_am) AS letzte_bearbeitung
        FROM antworten
        WHERE durchlauf >= 1
          AND aufgabe NOT LIKE 'KEY_%'
          AND aufgabe NOT LIKE 'BEREICH_%'
        GROUP BY pruefung_id
      )
      SELECT a.pruefung_id,
             COALESCE(m.pruefungsbereich, 'WISO') AS pruefungsbereich,
             a.durchlaeufe,
             a.ausgewertet,
             COALESCE(m.updated_am, a.letzte_bearbeitung) AS letzte_bearbeitung
      FROM answered a
      LEFT JOIN marker m ON m.pruefung_id = a.pruefung_id
      UNION ALL
      -- Marker ohne Antworten (z.B. nur Schlüssel gespeichert)
      SELECT m2.pruefung_id,
             m2.pruefungsbereich,
             0::bigint AS durchlaeufe,
             false AS ausgewertet,
             m2.updated_am AS letzte_bearbeitung
      FROM marker m2
      WHERE NOT EXISTS (
        SELECT 1 FROM answered a2 WHERE a2.pruefung_id = m2.pruefung_id
      )
      ORDER BY pruefung_id
    `;
    return result.map((r) => ({
      pruefung_id: r.pruefung_id,
      pruefungsbereich: r.pruefungsbereich,
      durchlaeufe: Number(r.durchlaeufe),
      ausgewertet: r.ausgewertet,
      letzte_bearbeitung: r.letzte_bearbeitung,
    }));
  }
}

import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class SeitenService {
  constructor(private readonly prisma: PrismaService) {}

  /** Alle Seiten eines Dokuments */
  findByDokument(dokumentId: number) {
    return this.prisma.seiten.findMany({
      where: { dokument_id: dokumentId },
      orderBy: { seiten_nr: 'asc' },
    });
  }

  /** Einzelne Seite */
  findOne(id: number) {
    return this.prisma.seiten.findUniqueOrThrow({
      where: { id },
      include: { dokumente: { include: { pruefungen: true } } },
    });
  }

  /** Volltext-Suche über alle OCR-Texte (PostgreSQL ts_vector) */
  async fullTextSearch(query: string, limit = 50) {
    const results = await this.prisma.$queryRaw<
      Array<{
        seiten_id: number;
        seiten_nr: number;
        dokument_id: number;
        dateiname: string;
        zeitraum_label: string;
        typ: string;
        headline: string;
        rank: number;
      }>
    >`
      SELECT
        s.id             AS seiten_id,
        s.seiten_nr,
        s.dokument_id,
        d.dateiname,
        p.zeitraum_label,
        d.typ,
        ts_headline('german', s.ocr_text,
          plainto_tsquery('german', ${query}),
          'MaxWords=40, MinWords=15, StartSel=<mark>, StopSel=</mark>'
        ) AS headline,
        ts_rank(to_tsvector('german', s.ocr_text),
          plainto_tsquery('german', ${query})
        ) AS rank
      FROM seiten s
      JOIN dokumente d ON d.id = s.dokument_id
      JOIN pruefungen p ON p.id = d.pruefung_id
      WHERE to_tsvector('german', s.ocr_text) @@ plainto_tsquery('german', ${query})
      ORDER BY rank DESC
      LIMIT ${limit}
    `;
    return results.map((r) => ({
      ...r,
      rank: Number(r.rank),
    }));
  }
}

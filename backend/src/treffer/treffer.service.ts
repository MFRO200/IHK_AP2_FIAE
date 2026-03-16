import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateTrefferDto } from './dto/treffer.dto';

@Injectable()
export class TrefferService {
  constructor(private readonly prisma: PrismaService) {}

  findAll(suchbegriffId?: number, dokumentId?: number) {
    return this.prisma.treffer.findMany({
      where: {
        ...(suchbegriffId ? { suchbegriff_id: suchbegriffId } : {}),
        ...(dokumentId ? { dokument_id: dokumentId } : {}),
      },
      include: {
        suchbegriff: true,
        dokument: { include: { pruefung: true } },
      },
      orderBy: { id: 'asc' },
    });
  }

  findOne(id: number) {
    return this.prisma.treffer.findUniqueOrThrow({
      where: { id },
      include: {
        suchbegriff: true,
        dokument: { include: { pruefung: true } },
      },
    });
  }

  create(dto: CreateTrefferDto) {
    return this.prisma.treffer.create({
      data: dto,
      include: { suchbegriff: true, dokument: true },
    });
  }

  remove(id: number) {
    return this.prisma.treffer.delete({ where: { id } });
  }

  /** Statistik: Treffer pro Section */
  async stats() {
    const result = await this.prisma.$queryRaw<
      Array<{ section: string; begriffe: bigint; treffer: bigint }>
    >`
      SELECT s.section,
             COUNT(DISTINCT s.id) AS begriffe,
             COUNT(t.id)          AS treffer
      FROM suchbegriffe s
      LEFT JOIN treffer t ON t.suchbegriff_id = s.id
      GROUP BY s.section
      ORDER BY s.section
    `;
    return result.map((r) => ({
      section: r.section,
      begriffe: Number(r.begriffe),
      treffer: Number(r.treffer),
    }));
  }

  /** Statistik: Treffer pro Prüfung und Section */
  async statsPerPruefung() {
    const result = await this.prisma.$queryRaw<
      Array<{
        pruefung_id: number;
        zeitraum_label: string;
        jahr: number;
        semester: string;
        section: string;
        begriffe: bigint;
        treffer: bigint;
      }>
    >`
      SELECT p.id AS pruefung_id,
             p.zeitraum_label,
             p.jahr,
             p.semester,
             s.section,
             COUNT(DISTINCT s.id) AS begriffe,
             COUNT(t.id)          AS treffer
      FROM treffer t
      JOIN suchbegriffe s ON t.suchbegriff_id = s.id
      JOIN dokumente d    ON t.dokument_id = d.id
      JOIN pruefungen p   ON d.pruefung_id = p.id
      GROUP BY p.id, p.zeitraum_label, p.jahr, p.semester, s.section
      ORDER BY p.jahr DESC, p.semester, s.section
    `;
    return result.map((r) => ({
      pruefung_id: r.pruefung_id,
      zeitraum_label: r.zeitraum_label,
      jahr: r.jahr,
      semester: r.semester,
      section: r.section,
      begriffe: Number(r.begriffe),
      treffer: Number(r.treffer),
    }));
  }

  /** Statistik: Treffer pro Prüfungsbereich (GA1, GA2, WISO, AP1, Sonstige) */
  async statsPerPruefungsbereich() {
    const result = await this.prisma.$queryRaw<
      Array<{ pruefungsbereich: string; dokumente: bigint; seiten: bigint; treffer: bigint; begriffe: bigint }>
    >`
      SELECT ds.pruefungsbereich,
             ds.dokumente,
             ds.seiten,
             COALESCE(ts.treffer, 0)  AS treffer,
             COALESCE(ts.begriffe, 0) AS begriffe
      FROM (
        SELECT COALESCE(pruefungsbereich, 'Sonstige') AS pruefungsbereich,
               COUNT(*)                    AS dokumente,
               COALESCE(SUM(seitenanzahl), 0) AS seiten
        FROM dokumente
        GROUP BY pruefungsbereich
      ) ds
      LEFT JOIN (
        SELECT COALESCE(d.pruefungsbereich, 'Sonstige') AS pruefungsbereich,
               COUNT(t.id)                  AS treffer,
               COUNT(DISTINCT t.suchbegriff_id) AS begriffe
        FROM treffer t
        JOIN dokumente d ON t.dokument_id = d.id
        GROUP BY d.pruefungsbereich
      ) ts ON ts.pruefungsbereich = ds.pruefungsbereich
      ORDER BY ts.treffer DESC NULLS LAST
    `;
    return result.map((r) => ({
      pruefungsbereich: r.pruefungsbereich,
      dokumente: Number(r.dokumente),
      seiten: Number(r.seiten),
      treffer: Number(r.treffer),
      begriffe: Number(r.begriffe),
    }));
  }

  /** Statistik: Treffer pro Themenblock */
  async statsPerThemenblock() {
    const result = await this.prisma.$queryRaw<
      Array<{ themenblock: string; begriffe: bigint; treffer: bigint }>
    >`
      SELECT COALESCE(s.themenblock, '(ohne Themenblock)') AS themenblock,
             COUNT(DISTINCT s.id) AS begriffe,
             COUNT(t.id)          AS treffer
      FROM suchbegriffe s
      LEFT JOIN treffer t ON t.suchbegriff_id = s.id
      WHERE s.themenblock IS NOT NULL
      GROUP BY s.themenblock
      ORDER BY COUNT(t.id) DESC
    `;
    return result.map((r) => ({
      themenblock: r.themenblock,
      begriffe: Number(r.begriffe),
      treffer: Number(r.treffer),
    }));
  }
}

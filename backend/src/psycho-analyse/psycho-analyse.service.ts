import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class PsychoAnalyseService {
  constructor(private readonly prisma: PrismaService) {}

  /** Alle Analysen mit Prüfungs-Info */
  findAll() {
    return this.prisma.psycho_analyse.findMany({
      include: {
        pruefung: {
          select: { id: true, zeitraum_label: true, jahr: true, semester: true },
        },
      },
      orderBy: [
        { pruefung: { jahr: 'desc' } },
        { pruefung: { semester: 'desc' } },
        { pruefungsbereich: 'asc' },
      ],
    });
  }

  /** Analysen für eine bestimmte Prüfung */
  findByPruefung(pruefungId: number) {
    return this.prisma.psycho_analyse.findMany({
      where: { pruefung_id: pruefungId },
      include: {
        pruefung: {
          select: { id: true, zeitraum_label: true, jahr: true, semester: true },
        },
      },
      orderBy: { pruefungsbereich: 'asc' },
    });
  }

  /** Einzelne Analyse */
  findOne(id: number) {
    return this.prisma.psycho_analyse.findUniqueOrThrow({
      where: { id },
      include: {
        pruefung: {
          select: { id: true, zeitraum_label: true, jahr: true, semester: true },
        },
      },
    });
  }

  /** Aggregierte Statistik über alle Prüfungen */
  async statistik() {
    const all = await this.prisma.psycho_analyse.findMany({
      select: {
        pruefungsbereich: true,
        bloom_wissen: true,
        bloom_verstehen: true,
        bloom_anwenden: true,
        bloom_analysieren: true,
        bloom_bewerten: true,
        bloom_erschaffen: true,
        afb1_prozent: true,
        afb2_prozent: true,
        afb3_prozent: true,
        operatoren: true,
        kompetenz_profil: true,
        kognitiver_anspruch: true,
        pruefung: {
          select: { jahr: true, semester: true, zeitraum_label: true },
        },
      },
      orderBy: [{ pruefung: { jahr: 'asc' } }, { pruefung: { semester: 'asc' } }],
    });

    // Aggregiere Bloom-Werte über alle Prüfungen
    const bloomGesamt = { wissen: 0, verstehen: 0, anwenden: 0, analysieren: 0, bewerten: 0, erschaffen: 0 };
    const afbGesamt = { afb1: 0, afb2: 0, afb3: 0 };
    const operatorenGesamt: Record<string, number> = {};

    for (const a of all) {
      bloomGesamt.wissen += a.bloom_wissen;
      bloomGesamt.verstehen += a.bloom_verstehen;
      bloomGesamt.anwenden += a.bloom_anwenden;
      bloomGesamt.analysieren += a.bloom_analysieren;
      bloomGesamt.bewerten += a.bloom_bewerten;
      bloomGesamt.erschaffen += a.bloom_erschaffen;

      afbGesamt.afb1 += Number(a.afb1_prozent);
      afbGesamt.afb2 += Number(a.afb2_prozent);
      afbGesamt.afb3 += Number(a.afb3_prozent);

      const ops = a.operatoren as Record<string, number>;
      for (const [op, count] of Object.entries(ops)) {
        operatorenGesamt[op] = (operatorenGesamt[op] || 0) + count;
      }
    }

    const n = all.length || 1;
    return {
      anzahl_analysen: all.length,
      bloom_durchschnitt: {
        wissen: Math.round(bloomGesamt.wissen / n * 10) / 10,
        verstehen: Math.round(bloomGesamt.verstehen / n * 10) / 10,
        anwenden: Math.round(bloomGesamt.anwenden / n * 10) / 10,
        analysieren: Math.round(bloomGesamt.analysieren / n * 10) / 10,
        bewerten: Math.round(bloomGesamt.bewerten / n * 10) / 10,
        erschaffen: Math.round(bloomGesamt.erschaffen / n * 10) / 10,
      },
      afb_durchschnitt: {
        afb1: Math.round(afbGesamt.afb1 / n * 10) / 10,
        afb2: Math.round(afbGesamt.afb2 / n * 10) / 10,
        afb3: Math.round(afbGesamt.afb3 / n * 10) / 10,
      },
      top_operatoren: Object.entries(operatorenGesamt)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15)
        .map(([op, count]) => ({ operator: op, count })),
      details: all,
    };
  }
}

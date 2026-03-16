import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class VersionenService {
  constructor(private readonly prisma: PrismaService) {}

  /** Alle Versionen eines Dokuments */
  findByDokument(dokumentId: number) {
    return this.prisma.dokument_versionen.findMany({
      where: { dokument_id: dokumentId },
      orderBy: { version_nr: 'asc' },
    });
  }

  /** Einzelne Version laden */
  findOne(id: number) {
    return this.prisma.dokument_versionen.findUnique({
      where: { id },
      include: { dokumente: true },
    });
  }

  /** Nächste Versionsnummer für ein Dokument */
  async nextVersionNr(dokumentId: number): Promise<number> {
    const max = await this.prisma.dokument_versionen.aggregate({
      where: { dokument_id: dokumentId },
      _max: { version_nr: true },
    });
    return (max._max.version_nr || 0) + 1;
  }

  /** Neue Version anlegen (nach Upload) */
  create(data: {
    dokument_id: number;
    version_nr: number;
    label: string;
    dateiname: string;
    storage_pfad: string;
    dateigroesse: number;
    kommentar?: string;
  }) {
    return this.prisma.dokument_versionen.create({ data });
  }

  /** Version löschen */
  remove(id: number) {
    return this.prisma.dokument_versionen.delete({ where: { id } });
  }
}

import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateDokumentDto, UpdateDokumentDto } from './dto/dokumente.dto';

@Injectable()
export class DokumenteService {
  constructor(private readonly prisma: PrismaService) {}

  findAll(pruefungId?: number, typ?: string, pruefungsbereich?: string) {
    return this.prisma.dokumente.findMany({
      where: {
        ...(pruefungId ? { pruefung_id: pruefungId } : {}),
        ...(typ ? { typ } : {}),
        ...(pruefungsbereich ? { pruefungsbereich } : {}),
      },
      include: { pruefung: true },
      orderBy: { id: 'asc' },
    });
  }

  findOneBasic(id: number) {
    return this.prisma.dokumente.findUnique({
      where: { id },
      select: { id: true, dateiname: true, pfad: true },
    });
  }

  findOne(id: number) {
    return this.prisma.dokumente.findUniqueOrThrow({
      where: { id },
      include: {
        pruefung: true,
        seiten: { orderBy: { seiten_nr: 'asc' } },
        treffer: { include: { suchbegriff: true } },
        versionen: { orderBy: { version_nr: 'asc' } },
      },
    });
  }

  create(dto: CreateDokumentDto) {
    return this.prisma.dokumente.create({ data: dto });
  }

  update(id: number, dto: UpdateDokumentDto) {
    return this.prisma.dokumente.update({ where: { id }, data: dto });
  }

  remove(id: number) {
    return this.prisma.dokumente.delete({ where: { id } });
  }
}

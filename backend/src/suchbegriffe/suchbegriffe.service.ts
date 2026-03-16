import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateSuchbegriffDto, UpdateSuchbegriffDto } from './dto/suchbegriffe.dto';

@Injectable()
export class SuchbegriffeService {
  constructor(private readonly prisma: PrismaService) {}

  findAll(section?: string) {
    return this.prisma.suchbegriffe.findMany({
      where: section ? { section } : {},
      orderBy: [{ treffer_anzahl: 'desc' }, { begriff: 'asc' }],
    });
  }

  findOne(id: number) {
    return this.prisma.suchbegriffe.findUniqueOrThrow({
      where: { id },
      include: {
        treffer: {
          include: { dokumente: { include: { pruefungen: true } } },
          orderBy: { dokumente: { id: 'asc' } },
        },
      },
    });
  }

  /** Suche nach Begriff-Name (case-insensitive) */
  search(q: string) {
    return this.prisma.suchbegriffe.findMany({
      where: { begriff: { contains: q, mode: 'insensitive' } },
      orderBy: { treffer_anzahl: 'desc' },
      take: 50,
    });
  }

  create(dto: CreateSuchbegriffDto) {
    return this.prisma.suchbegriffe.create({ data: dto });
  }

  update(id: number, dto: UpdateSuchbegriffDto) {
    return this.prisma.suchbegriffe.update({ where: { id }, data: dto });
  }

  remove(id: number) {
    return this.prisma.suchbegriffe.delete({ where: { id } });
  }
}

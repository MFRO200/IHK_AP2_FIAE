import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreatePruefungDto, UpdatePruefungDto } from './dto/pruefungen.dto';

@Injectable()
export class PruefungenService {
  constructor(private readonly prisma: PrismaService) {}

  findAll() {
    return this.prisma.pruefungen.findMany({
      orderBy: [{ jahr: 'asc' }, { semester: 'asc' }],
    });
  }

  findOne(id: number) {
    return this.prisma.pruefungen.findUniqueOrThrow({
      where: { id },
      include: { dokumente: true },
    });
  }

  create(dto: CreatePruefungDto) {
    return this.prisma.pruefungen.create({ data: dto });
  }

  update(id: number, dto: UpdatePruefungDto) {
    return this.prisma.pruefungen.update({ where: { id }, data: dto });
  }

  remove(id: number) {
    return this.prisma.pruefungen.delete({ where: { id } });
  }
}

import { Controller, Get, Param, ParseIntPipe } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { PsychoAnalyseService } from './psycho-analyse.service';

/** Prisma gibt die Relation als 'pruefungen' (Tabellenname) zurück,
 *  das Frontend erwartet aber 'pruefung' (Singular). */
function mapPruefung(item: any) {
  if (!item) return item;
  const { pruefungen, ...rest } = item;
  return { ...rest, pruefung: pruefungen };
}

@ApiTags('Psychologische Analyse')
@Controller('psycho-analyse')
export class PsychoAnalyseController {
  constructor(private readonly service: PsychoAnalyseService) {}

  @Get()
  @ApiOperation({ summary: 'Alle psychologischen Analysen' })
  async findAll() {
    const items = await this.service.findAll();
    return items.map(mapPruefung);
  }

  @Get('statistik')
  @ApiOperation({ summary: 'Aggregierte Statistik über alle Prüfungen' })
  async statistik() {
    const stat = await this.service.statistik();
    return {
      ...stat,
      details: stat.details.map(mapPruefung),
    };
  }

  @Get('trainingsplan')
  @ApiOperation({ summary: 'Trainingsplan mit Prognose und Empfehlungen für AP2 Sommer 2026' })
  trainingsplan() {
    return this.service.trainingsplan();
  }

  @Get('pruefung/:pruefungId')
  @ApiOperation({ summary: 'Analysen für eine bestimmte Prüfung' })
  async findByPruefung(@Param('pruefungId', ParseIntPipe) pruefungId: number) {
    const items = await this.service.findByPruefung(pruefungId);
    return items.map(mapPruefung);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelne Analyse' })
  async findOne(@Param('id', ParseIntPipe) id: number) {
    const item = await this.service.findOne(id);
    return mapPruefung(item);
  }
}

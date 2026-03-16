import { Controller, Get, Param, ParseIntPipe } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { PsychoAnalyseService } from './psycho-analyse.service';

@ApiTags('Psychologische Analyse')
@Controller('psycho-analyse')
export class PsychoAnalyseController {
  constructor(private readonly service: PsychoAnalyseService) {}

  @Get()
  @ApiOperation({ summary: 'Alle psychologischen Analysen' })
  findAll() {
    return this.service.findAll();
  }

  @Get('statistik')
  @ApiOperation({ summary: 'Aggregierte Statistik über alle Prüfungen' })
  statistik() {
    return this.service.statistik();
  }

  @Get('trainingsplan')
  @ApiOperation({ summary: 'Trainingsplan mit Prognose und Empfehlungen für AP2 Sommer 2026' })
  trainingsplan() {
    return this.service.trainingsplan();
  }

  @Get('pruefung/:pruefungId')
  @ApiOperation({ summary: 'Analysen für eine bestimmte Prüfung' })
  findByPruefung(@Param('pruefungId', ParseIntPipe) pruefungId: number) {
    return this.service.findByPruefung(pruefungId);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelne Analyse' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }
}

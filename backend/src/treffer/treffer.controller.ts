import {
  Controller, Get, Post, Delete,
  Param, Body, Query, ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { TrefferService } from './treffer.service';
import { CreateTrefferDto } from './dto/treffer.dto';

@ApiTags('Treffer')
@Controller('treffer')
export class TrefferController {
  constructor(private readonly service: TrefferService) {}

  @Get()
  @ApiOperation({ summary: 'Alle Treffer auflisten (optional filtern)' })
  @ApiQuery({ name: 'suchbegriffId', required: false, type: Number })
  @ApiQuery({ name: 'dokumentId', required: false, type: Number })
  findAll(
    @Query('suchbegriffId') suchbegriffId?: string,
    @Query('dokumentId') dokumentId?: string,
  ) {
    return this.service.findAll(
      suchbegriffId ? parseInt(suchbegriffId, 10) : undefined,
      dokumentId ? parseInt(dokumentId, 10) : undefined,
    );
  }

  @Get('stats')
  @ApiOperation({ summary: 'Treffer-Statistik pro Section (A/B/C/D/X)' })
  stats() {
    return this.service.stats();
  }

  @Get('stats/pruefungen')
  @ApiOperation({ summary: 'Treffer-Statistik pro Pruefung und Section' })
  statsPerPruefung() {
    return this.service.statsPerPruefung();
  }

  @Get('stats/pruefungsbereich')
  @ApiOperation({ summary: 'Treffer-Statistik pro Prüfungsbereich (GA1, GA2, WISO, AP1)' })
  statsPerPruefungsbereich() {
    return this.service.statsPerPruefungsbereich();
  }

  @Get('stats/themenblock')
  @ApiOperation({ summary: 'Treffer-Statistik pro Themenblock' })
  statsPerThemenblock() {
    return this.service.statsPerThemenblock();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelner Treffer mit Details' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: 'Neuen Treffer anlegen' })
  create(@Body() dto: CreateTrefferDto) {
    return this.service.create(dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Treffer löschen' })
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.service.remove(id);
  }
}

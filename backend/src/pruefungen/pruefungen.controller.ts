import {
  Controller, Get, Post, Put, Delete,
  Param, Body, ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { PruefungenService } from './pruefungen.service';
import { CreatePruefungDto, UpdatePruefungDto } from './dto/pruefungen.dto';

@ApiTags('Prüfungen')
@Controller('pruefungen')
export class PruefungenController {
  constructor(private readonly service: PruefungenService) {}

  @Get()
  @ApiOperation({ summary: 'Alle Prüfungszeiträume auflisten' })
  findAll() {
    return this.service.findAll();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelner Prüfungszeitraum mit Dokumenten' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: 'Neuen Prüfungszeitraum anlegen' })
  create(@Body() dto: CreatePruefungDto) {
    return this.service.create(dto);
  }

  @Put(':id')
  @ApiOperation({ summary: 'Prüfungszeitraum aktualisieren' })
  update(
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdatePruefungDto,
  ) {
    return this.service.update(id, dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Prüfungszeitraum löschen' })
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.service.remove(id);
  }
}

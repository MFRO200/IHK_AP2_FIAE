import {
  Controller, Get, Post, Put, Delete,
  Param, Body, Query, ParseIntPipe,
  UploadedFile, UseInterceptors,
  Res, NotFoundException, StreamableFile, BadRequestException,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ApiTags, ApiOperation, ApiQuery, ApiConsumes, ApiBody } from '@nestjs/swagger';
import { AntwortenService } from './antworten.service';
import { CreateAntwortDto, UpdateAntwortDto } from './dto/antworten.dto';
import { Response } from 'express';
import { createReadStream, existsSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const WORKSPACE_ROOT = join(__dirname, '..', '..', '..');

@ApiTags('Antworten')
@Controller('antworten')
export class AntwortenController {
  constructor(private readonly service: AntwortenService) {}

  @Get('pruefung/:pruefungId')
  @ApiOperation({ summary: 'Alle eigenen Antworten einer Prüfung (optional nach Durchlauf)' })
  @ApiQuery({ name: 'durchlauf', required: false, type: Number })
  findByPruefung(
    @Param('pruefungId', ParseIntPipe) pruefungId: number,
    @Query('durchlauf') durchlauf?: string,
  ) {
    const dl = durchlauf != null ? Number(durchlauf) : undefined;
    return this.service.findByPruefung(pruefungId, dl);
  }

  @Get('pruefung/:pruefungId/durchlaeufe')
  @ApiOperation({ summary: 'Alle Durchläufe einer Prüfung mit Statistiken' })
  durchlaeufe(@Param('pruefungId', ParseIntPipe) pruefungId: number) {
    return this.service.durchlaeufe(pruefungId);
  }

  @Get('stats')
  @ApiOperation({ summary: 'Übersicht: Bearbeitete Prüfungen mit Punktestand' })
  stats() {
    return this.service.stats();
  }

  @Get('bearbeitungsstatus')
  @ApiOperation({ summary: 'Welche Prüfungen + Bereiche wurden bereits geübt?' })
  bearbeitungsStatus() {
    return this.service.bearbeitungsStatus();
  }

  @Get('alle-bilder')
  @ApiOperation({ summary: 'Alle hochgeladenen Bilder/PDFs mit Prüfungs- und Aufgaben-Info' })
  alleBilder() {
    return this.service.alleBilder();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelne Antwort' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: 'Antwort anlegen oder aktualisieren (Upsert)' })
  upsert(@Body() dto: CreateAntwortDto) {
    return this.service.upsert(dto);
  }

  @Put(':id')
  @ApiOperation({ summary: 'Antwort aktualisieren' })
  update(
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateAntwortDto,
  ) {
    return this.service.update(id, dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Antwort löschen' })
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.service.remove(id);
  }

  /* ═══════════════ Bilder (Antwort-Fotos) ═══════════════ */

  @Get(':antwortId/bilder')
  @ApiOperation({ summary: 'Alle Bilder einer Antwort' })
  findBilder(@Param('antwortId', ParseIntPipe) antwortId: number) {
    return this.service.findBilder(antwortId);
  }

  @Get(':antwortId/bilder/:bildId/file')
  @ApiOperation({ summary: 'Bild-Datei streamen' })
  async serveBild(
    @Param('antwortId', ParseIntPipe) antwortId: number,
    @Param('bildId', ParseIntPipe) bildId: number,
    @Res({ passthrough: true }) res: Response,
  ): Promise<StreamableFile> {
    const bild = await this.service.findBild(bildId);
    if (!bild || bild.antwort_id !== antwortId) {
      throw new NotFoundException('Bild nicht gefunden');
    }
    const filePath = join(WORKSPACE_ROOT, bild.storage_pfad);
    if (!existsSync(filePath)) {
      throw new NotFoundException(`Bild-Datei nicht gefunden: ${bild.storage_pfad}`);
    }
    const ext = bild.dateiname.split('.').pop()?.toLowerCase() || 'jpg';
    const mimeMap: Record<string, string> = {
      jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png',
      gif: 'image/gif', webp: 'image/webp', bmp: 'image/bmp',
      pdf: 'application/pdf',
    };
    res.set({
      'Content-Type': mimeMap[ext] || 'application/octet-stream',
      'Content-Disposition': `inline; filename="${encodeURIComponent(bild.dateiname)}"`,
      'Cache-Control': 'public, max-age=86400',
    });
    return new StreamableFile(createReadStream(filePath));
  }

  @Post(':antwortId/bilder')
  @ApiOperation({ summary: 'Bild zu einer Antwort hochladen' })
  @ApiConsumes('multipart/form-data')
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        file: { type: 'string', format: 'binary' },
      },
    },
  })
  @UseInterceptors(FileInterceptor('file'))
  async uploadBild(
    @Param('antwortId', ParseIntPipe) antwortId: number,
    @UploadedFile() file: Express.Multer.File,
  ) {
    if (!file) throw new BadRequestException('Keine Datei hochgeladen');

    // Antwort laden um pruefung_id + aufgabe für den Pfad zu bekommen
    const antwort = await this.service.findOne(antwortId);
    if (!antwort) throw new NotFoundException('Antwort nicht gefunden');

    const timestamp = Date.now();
    const safeOriginal = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_');
    const safeFilename = `${timestamp}_${safeOriginal}`;

    // Speichern unter storage/antworten/<pruefungId>/<aufgabe>/
    const safeAufgabe = antwort.aufgabe.replace(/[^a-zA-Z0-9_.-]/g, '_');
    const targetDir = join(
      WORKSPACE_ROOT, 'storage', 'antworten',
      String(antwort.pruefung_id), safeAufgabe,
    );
    mkdirSync(targetDir, { recursive: true });
    const targetPath = join(targetDir, safeFilename);
    writeFileSync(targetPath, file.buffer);

    const storagePfad = `storage/antworten/${antwort.pruefung_id}/${safeAufgabe}/${safeFilename}`;

    return this.service.createBild({
      antwort_id: antwortId,
      dateiname: file.originalname,
      storage_pfad: storagePfad,
      dateigroesse: file.size,
    });
  }

  @Delete(':antwortId/bilder/:bildId')
  @ApiOperation({ summary: 'Bild löschen' })
  async removeBild(
    @Param('antwortId', ParseIntPipe) antwortId: number,
    @Param('bildId', ParseIntPipe) bildId: number,
  ) {
    const bild = await this.service.findBild(bildId);
    if (!bild || bild.antwort_id !== antwortId) {
      throw new NotFoundException('Bild nicht gefunden');
    }
    // Datei löschen
    const filePath = join(WORKSPACE_ROOT, bild.storage_pfad);
    if (existsSync(filePath)) {
      const { unlinkSync } = require('fs');
      unlinkSync(filePath);
    }
    return this.service.removeBild(bildId);
  }
}

import {
  Controller, Get, Post, Delete,
  Param, ParseIntPipe, UploadedFile,
  UseInterceptors, Res, NotFoundException,
  StreamableFile, Body, BadRequestException,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ApiTags, ApiOperation, ApiConsumes, ApiBody } from '@nestjs/swagger';
import { VersionenService } from './versionen.service';
import { Response } from 'express';
import { createReadStream, existsSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';

const WORKSPACE_ROOT = join(__dirname, '..', '..', '..');

@ApiTags('Versionen')
@Controller('dokumente/:dokumentId/versionen')
export class VersionenController {
  constructor(private readonly service: VersionenService) {}

  @Get()
  @ApiOperation({ summary: 'Alle Versionen eines Dokuments' })
  findAll(@Param('dokumentId', ParseIntPipe) dokumentId: number) {
    return this.service.findByDokument(dokumentId);
  }

  @Get(':versionId/pdf')
  @ApiOperation({ summary: 'PDF einer bestimmten Version streamen' })
  async servePdf(
    @Param('dokumentId', ParseIntPipe) dokumentId: number,
    @Param('versionId', ParseIntPipe) versionId: number,
    @Res({ passthrough: true }) res: Response,
  ): Promise<StreamableFile> {
    const version = await this.service.findOne(versionId);
    if (!version || version.dokument_id !== dokumentId) {
      throw new NotFoundException('Version nicht gefunden');
    }

    const filePath = join(WORKSPACE_ROOT, version.storage_pfad);
    if (!existsSync(filePath)) {
      throw new NotFoundException(`PDF nicht gefunden: ${version.storage_pfad}`);
    }

    const stream = createReadStream(filePath);
    res.set({
      'Content-Type': 'application/pdf',
      'Content-Disposition': `inline; filename="${encodeURIComponent(version.dateiname)}"`,
    });
    return new StreamableFile(stream);
  }

  @Post('upload')
  @ApiOperation({ summary: 'Neue Version hochladen (bearbeitetes PDF)' })
  @ApiConsumes('multipart/form-data')
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        file: { type: 'string', format: 'binary' },
        label: { type: 'string', example: 'Mit Notizen' },
        kommentar: { type: 'string', example: 'Markierungen zu Kapitel 3' },
      },
    },
  })
  @UseInterceptors(FileInterceptor('file'))
  async upload(
    @Param('dokumentId', ParseIntPipe) dokumentId: number,
    @UploadedFile() file: Express.Multer.File,
    @Body('label') label?: string,
    @Body('kommentar') kommentar?: string,
  ) {
    if (!file) throw new BadRequestException('Keine Datei hochgeladen');

    const nextNr = await this.service.nextVersionNr(dokumentId);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const safeFilename = `v${nextNr}_${timestamp}_${file.originalname}`;

    // Speichern unter storage/pdfs/versionen/<dokumentId>/
    const targetDir = join(WORKSPACE_ROOT, 'storage', 'pdfs', 'versionen', String(dokumentId));
    mkdirSync(targetDir, { recursive: true });
    const targetPath = join(targetDir, safeFilename);
    writeFileSync(targetPath, file.buffer);

    const storagePfad = `storage/pdfs/versionen/${dokumentId}/${safeFilename}`;

    return this.service.create({
      dokument_id: dokumentId,
      version_nr: nextNr,
      label: label || `Version ${nextNr}`,
      dateiname: safeFilename,
      storage_pfad: storagePfad,
      dateigroesse: file.size,
      kommentar: kommentar || undefined,
    });
  }

  @Delete(':versionId')
  @ApiOperation({ summary: 'Version löschen (nicht das Original)' })
  async remove(
    @Param('dokumentId', ParseIntPipe) dokumentId: number,
    @Param('versionId', ParseIntPipe) versionId: number,
  ) {
    const version = await this.service.findOne(versionId);
    if (!version || version.dokument_id !== dokumentId) {
      throw new NotFoundException('Version nicht gefunden');
    }
    if (version.version_nr === 1) {
      throw new BadRequestException('Original-Version kann nicht gelöscht werden');
    }
    return this.service.remove(versionId);
  }
}

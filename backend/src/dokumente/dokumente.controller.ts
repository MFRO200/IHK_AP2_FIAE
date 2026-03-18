import {
  Controller, Get, Post, Put, Delete,
  Param, Body, Query, ParseIntPipe,
  Res, NotFoundException, StreamableFile, Header,
  UploadedFile, UseInterceptors, BadRequestException,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ApiTags, ApiOperation, ApiQuery, ApiConsumes, ApiBody } from '@nestjs/swagger';
import { DokumenteService } from './dokumente.service';
import { CreateDokumentDto, UpdateDokumentDto } from './dto/dokumente.dto';
import { Response } from 'express';
import { createReadStream, existsSync, writeFileSync, mkdirSync, statSync } from 'fs';
import { join } from 'path';
import { execFile } from 'child_process';
import { PrismaService } from '../prisma/prisma.service';
import { Logger } from '@nestjs/common';
import { homedir } from 'os';

// Workspace-Root (eine Ebene über backend/)
const WORKSPACE_ROOT = join(__dirname, '..', '..', '..');

/** Pfad auflösen: ~/ → Home-Verzeichnis, zip:// → ignorieren, relativ → WORKSPACE_ROOT */
function resolvePdfPath(pfad: string): string | null {
  if (!pfad) return null;
  // ~/... → absoluten Home-Pfad auflösen
  if (pfad.startsWith('~/') || pfad.startsWith('~\\')) {
    const resolved = join(homedir(), pfad.substring(2));
    if (existsSync(resolved)) return resolved;
  }
  // zip:// Pfade können nicht direkt aufgelöst werden
  if (pfad.startsWith('zip://')) return null;
  // Relativer Pfad → relativ zum Workspace
  const resolved = join(WORKSPACE_ROOT, pfad);
  if (existsSync(resolved)) return resolved;
  return null;
}

// Python-Interpreter im venv
const PYTHON_EXE = join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe');
const SCAN_SCRIPT = join(WORKSPACE_ROOT, 'scan_dokument.py');
const EXTRACT_WISO_SCRIPT = join(WORKSPACE_ROOT, 'extract_wiso_answers.py');
const OCR_EXTRACT_SCRIPT = join(WORKSPACE_ROOT, 'ocr_extract_ga_antworten.py');

@ApiTags('Dokumente')
@Controller('dokumente')
export class DokumenteController {
  private readonly logger = new Logger(DokumenteController.name);

  constructor(
    private readonly service: DokumenteService,
    private readonly prisma: PrismaService,
  ) {}

  /** Startet scan_dokument.py als Child-Process und gibt das JSON-Ergebnis zurück */
  private runScan(dokumentId: number): Promise<any> {
    return new Promise((resolve, reject) => {
      execFile(
        PYTHON_EXE,
        [SCAN_SCRIPT, String(dokumentId)],
        { cwd: WORKSPACE_ROOT, timeout: 120_000, maxBuffer: 5 * 1024 * 1024 },
        (err, stdout, stderr) => {
          if (stderr) this.logger.warn(`scan stderr: ${stderr}`);
          if (err) {
            this.logger.error(`Scan fehlgeschlagen für Dokument ${dokumentId}: ${err.message}`);
            return reject(err);
          }
          try {
            resolve(JSON.parse(stdout));
          } catch {
            resolve({ raw: stdout });
          }
        },
      );
    });
  }

  /** Startet extract_wiso_answers.py und gibt den Lösungsschlüssel zurück */
  private runExtractWiso(dokumentId: number): Promise<any> {
    return new Promise((resolve, reject) => {
      execFile(
        PYTHON_EXE,
        [EXTRACT_WISO_SCRIPT, String(dokumentId)],
        { cwd: WORKSPACE_ROOT, timeout: 60_000, maxBuffer: 5 * 1024 * 1024 },
        (err, stdout, stderr) => {
          if (stderr) this.logger.warn(`extract-wiso stderr: ${stderr}`);
          if (err) {
            this.logger.error(`WISO-Extraktion fehlgeschlagen für Dokument ${dokumentId}: ${err.message}`);
            return reject(err);
          }
          try {
            resolve(JSON.parse(stdout));
          } catch {
            resolve({ raw: stdout });
          }
        },
      );
    });
  }

  /** Startet ocr_extract_ga_antworten.py und gibt den extrahierten Text zurück */
  private runOcrExtract(dokumentId: number): Promise<any> {
    return new Promise((resolve, reject) => {
      execFile(
        PYTHON_EXE,
        [OCR_EXTRACT_SCRIPT, String(dokumentId)],
        { cwd: WORKSPACE_ROOT, timeout: 180_000, maxBuffer: 10 * 1024 * 1024 },
        (err, stdout, stderr) => {
          if (stderr) this.logger.warn(`ocr-extract stderr: ${stderr}`);
          if (err) {
            this.logger.error(`OCR-Extraktion fehlgeschlagen für Dokument ${dokumentId}: ${err.message}`);
            return reject(err);
          }
          try {
            resolve(JSON.parse(stdout));
          } catch {
            resolve({ raw: stdout });
          }
        },
      );
    });
  }

  @Get()
  @ApiOperation({ summary: 'Alle Dokumente auflisten (optional filtern)' })
  @ApiQuery({ name: 'pruefungId', required: false, type: Number })
  @ApiQuery({ name: 'typ', required: false, enum: ['Aufgabe', 'Lösung', 'Handreichung'] })
  @ApiQuery({ name: 'pruefungsbereich', required: false, enum: ['GA1', 'GA2', 'WISO', 'AP1', 'Sonstige'] })
  findAll(
    @Query('pruefungId') pruefungId?: string,
    @Query('typ') typ?: string,
    @Query('pruefungsbereich') pruefungsbereich?: string,
  ) {
    return this.service.findAll(
      pruefungId ? parseInt(pruefungId, 10) : undefined,
      typ,
      pruefungsbereich,
    );
  }

  @Get(':id/pdf')
  @ApiOperation({ summary: 'PDF-Datei eines Dokuments streamen (bevorzugt aus storage/)' })
  async servePdf(
    @Param('id', ParseIntPipe) id: number,
    @Res({ passthrough: true }) res: Response,
  ): Promise<StreamableFile> {
    const doc = await this.service.findOneBasic(id);
    if (!doc) throw new NotFoundException('Dokument nicht gefunden');

    // Bevorzugt Version 1 (Original in storage/) verwenden
    const v1 = await this.prisma.dokument_versionen.findFirst({
      where: { dokument_id: id, version_nr: 1 },
    });

    let filePath: string | null = null;

    // 1. Bevorzugt Version 1 (Original in storage/) verwenden
    if (v1) {
      const storagePath = join(WORKSPACE_ROOT, v1.storage_pfad);
      if (existsSync(storagePath)) {
        filePath = storagePath;
      }
    }

    // 2. Fallback: Pfad aus DB auflösen (~/, relativ, etc.)
    if (!filePath) {
      filePath = resolvePdfPath(doc.pfad);
    }

    if (!filePath) {
      throw new NotFoundException(`PDF nicht gefunden: ${doc.pfad}`);
    }

    const stream = createReadStream(filePath);
    res.set({
      'Content-Type': 'application/pdf',
      'Content-Disposition': `inline; filename="${encodeURIComponent(doc.dateiname)}"`,
    });
    return new StreamableFile(stream);
  }

  @Get(':id/download')
  @ApiOperation({ summary: 'PDF-Datei zum Download' })
  async downloadPdf(
    @Param('id', ParseIntPipe) id: number,
    @Res({ passthrough: true }) res: Response,
  ): Promise<StreamableFile> {
    const doc = await this.service.findOneBasic(id);
    if (!doc) throw new NotFoundException('Dokument nicht gefunden');

    const filePath = resolvePdfPath(doc.pfad);
    if (!filePath) {
      throw new NotFoundException(`PDF nicht gefunden: ${doc.pfad}`);
    }

    const stream = createReadStream(filePath);
    res.set({
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="${encodeURIComponent(doc.dateiname)}"`,
    });
    return new StreamableFile(stream);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelnes Dokument mit Seiten und Treffern' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: 'Neues Dokument anlegen' })
  create(@Body() dto: CreateDokumentDto) {
    return this.service.create(dto);
  }

  @Post('upload')
  @ApiOperation({ summary: 'PDF hochladen und als neues Dokument anlegen' })
  @ApiConsumes('multipart/form-data')
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        file: { type: 'string', format: 'binary' },
        pruefung_id: { type: 'number' },
        typ: { type: 'string', enum: ['Aufgabe', 'Lösung', 'Handreichung', 'Belegsatz'] },
        pruefungsbereich: { type: 'string', enum: ['GA1', 'GA2', 'WISO', 'AP1', 'Sonstige'] },
      },
    },
  })
  @UseInterceptors(FileInterceptor('file'))
  async upload(
    @UploadedFile() file: Express.Multer.File,
    @Body('pruefung_id') pruefungIdStr: string,
    @Body('typ') typ?: string,
    @Body('pruefungsbereich') pruefungsbereich?: string,
  ) {
    if (!file) throw new BadRequestException('Keine Datei hochgeladen');
    if (!pruefungIdStr) throw new BadRequestException('pruefung_id ist erforderlich');
    
    const pruefung_id = parseInt(pruefungIdStr, 10);
    const pruefung = await this.prisma.pruefungen.findUnique({ where: { id: pruefung_id } });
    if (!pruefung) throw new NotFoundException(`Prüfung ${pruefung_id} nicht gefunden`);

    // Ordner: storage/pdfs/<ordner_name>/
    const targetDir = join(WORKSPACE_ROOT, 'storage', 'pdfs', pruefung.ordner_name);
    mkdirSync(targetDir, { recursive: true });
    const safeFilename = file.originalname.replace(/[^a-zA-Z0-9äöüÄÖÜß._\- ()]/g, '_');
    const targetPath = join(targetDir, safeFilename);
    writeFileSync(targetPath, file.buffer);

    const relativePfad = `storage/pdfs/${pruefung.ordner_name}/${safeFilename}`;

    // Dokument in DB anlegen
    const dok = await this.service.create({
      pruefung_id,
      dateiname: safeFilename,
      pfad: relativePfad,
      typ: typ || 'Aufgabe',
      dateigroesse: file.size,
      seitenanzahl: 0,
      pruefungsbereich: pruefungsbereich || undefined,
    });

    // Version 1 (Original) anlegen
    await this.prisma.dokument_versionen.create({
      data: {
        dokument_id: dok.id,
        version_nr: 1,
        label: 'Original',
        dateiname: safeFilename,
        storage_pfad: relativePfad,
        dateigroesse: file.size,
      },
    });

    // Auto-Scan: Begriffe im Hintergrund suchen (fire & forget)
    this.runScan(dok.id)
      .then(r => this.logger.log(`Auto-Scan Dokument ${dok.id}: ${r.treffer_count ?? 0} Treffer, OCR=${r.ocr_used}`))
      .catch(e => this.logger.error(`Auto-Scan Dokument ${dok.id} fehlgeschlagen: ${e.message}`));

    return dok;
  }

  @Post(':id/ocr-text')
  @ApiOperation({ summary: 'PDF-Text per OCR extrahieren (Tesseract)' })
  async ocrText(@Param('id', ParseIntPipe) id: number) {
    const doc = await this.service.findOneBasic(id);
    if (!doc) throw new NotFoundException(`Dokument ${id} nicht gefunden`);

    try {
      const result = await this.runOcrExtract(id);
      return result;
    } catch (err) {
      throw new BadRequestException(`OCR-Extraktion fehlgeschlagen: ${err.message}`);
    }
  }

  @Get(':id/extract-answers')
  @ApiOperation({ summary: 'WISO-Lösungsschlüssel aus PDF extrahieren' })
  async extractAnswers(@Param('id', ParseIntPipe) id: number) {
    const doc = await this.service.findOneBasic(id);
    if (!doc) throw new NotFoundException(`Dokument ${id} nicht gefunden`);

    try {
      const result = await this.runExtractWiso(id);
      return result;
    } catch (err) {
      throw new BadRequestException(`Extraktion fehlgeschlagen: ${err.message}`);
    }
  }

  @Post(':id/scan')
  @ApiOperation({ summary: 'Dokument gegen alle Suchbegriffe scannen (mit OCR-Fallback)' })
  async scanDocument(@Param('id', ParseIntPipe) id: number) {
    // Prüfe ob Dokument existiert
    const doc = await this.service.findOneBasic(id);
    if (!doc) throw new NotFoundException(`Dokument ${id} nicht gefunden`);

    try {
      const result = await this.runScan(id);
      return result;
    } catch (err) {
      throw new BadRequestException(`Scan fehlgeschlagen: ${err.message}`);
    }
  }

  @Put(':id')
  @ApiOperation({ summary: 'Dokument aktualisieren' })
  update(
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateDokumentDto,
  ) {
    return this.service.update(id, dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Dokument löschen' })
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.service.remove(id);
  }
}

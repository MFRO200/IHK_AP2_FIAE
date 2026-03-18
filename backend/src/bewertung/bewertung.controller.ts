import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  ParseIntPipe,
  Query,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { BewertungService } from './bewertung.service';
import { BewertungRequestDto } from './bewertung.dto';

@ApiTags('bewertung')
@Controller('bewertung')
export class BewertungController {
  constructor(private readonly service: BewertungService) {}

  @Post('bewerten')
  @ApiOperation({ summary: 'Einzelne Antwort bewerten lassen' })
  bewerten(@Body() body: BewertungRequestDto) {
    return this.service.bewerten(body);
  }

  @Post('bewerten/pruefung/:pruefungId')
  @ApiOperation({ summary: 'Alle offenen Antworten einer Prüfung bewerten' })
  @ApiQuery({ name: 'provider', enum: ['ollama', 'openai', 'perplexity'] })
  @ApiQuery({ name: 'model', required: false })
  @ApiQuery({ name: 'durchlauf', required: false, type: Number })
  bewertenPruefung(
    @Param('pruefungId', ParseIntPipe) pruefungId: number,
    @Query('provider') provider: 'ollama' | 'openai' | 'perplexity' = 'ollama',
    @Query('model') model?: string,
    @Query('durchlauf') durchlauf?: string,
  ) {
    const dl = durchlauf != null ? Number(durchlauf) : undefined;
    return this.service.bewertenPruefung(pruefungId, provider, model, dl);
  }

  @Post('analyse-dokument/:dokumentId')
  @ApiOperation({ summary: 'Bearbeitete PDF per OCR+KI analysieren und Aufgaben extrahieren' })
  @ApiQuery({ name: 'provider', enum: ['ollama', 'openai', 'perplexity'] })
  @ApiQuery({ name: 'model', required: false })
  analyseDokument(
    @Param('dokumentId', ParseIntPipe) dokumentId: number,
    @Query('provider') provider: 'ollama' | 'openai' | 'perplexity' = 'perplexity',
    @Query('model') model?: string,
  ) {
    return this.service.analyseDokumentOcr(dokumentId, provider, model);
  }

  @Post('extract-fragen/:dokumentId')
  @ApiOperation({ summary: 'Fragen aus Aufgabe-PDF extrahieren und als Musterlösungen speichern' })
  @ApiQuery({ name: 'provider', enum: ['ollama', 'openai', 'perplexity'] })
  @ApiQuery({ name: 'model', required: false })
  extractFragen(
    @Param('dokumentId', ParseIntPipe) dokumentId: number,
    @Query('provider') provider: 'ollama' | 'openai' | 'perplexity' = 'perplexity',
    @Query('model') model?: string,
  ) {
    return this.service.extractFragenFromDokument(dokumentId, provider, model);
  }

  @Post('extract-loesungen/:dokumentId')
  @ApiOperation({ summary: 'Lösungen aus Lösung/Handreichung-PDF extrahieren und in Musterlösungen speichern' })
  @ApiQuery({ name: 'provider', enum: ['ollama', 'openai', 'perplexity'] })
  @ApiQuery({ name: 'model', required: false })
  extractLoesungen(
    @Param('dokumentId', ParseIntPipe) dokumentId: number,
    @Query('provider') provider: 'ollama' | 'openai' | 'perplexity' = 'perplexity',
    @Query('model') model?: string,
  ) {
    return this.service.extractLoesungenFromDokument(dokumentId, provider, model);
  }

  @Get('antwort/:antwortId')
  @ApiOperation({ summary: 'Bewertungen für eine Antwort abrufen' })
  findByAntwort(@Param('antwortId', ParseIntPipe) antwortId: number) {
    return this.service.findByAntwort(antwortId);
  }

  @Get('pruefung/:pruefungId')
  @ApiOperation({ summary: 'Alle Bewertungen einer Prüfung' })
  findByPruefung(@Param('pruefungId', ParseIntPipe) pruefungId: number) {
    return this.service.findByPruefung(pruefungId);
  }

  @Get('musterloesungen/:pruefungId')
  @ApiOperation({ summary: 'Musterlösungen einer Prüfung' })
  findMusterloesungen(@Param('pruefungId', ParseIntPipe) pruefungId: number) {
    return this.service.findMusterloesungen(pruefungId);
  }

  @Get('provider/:provider')
  @ApiOperation({ summary: 'LLM-Provider Verfügbarkeit prüfen' })
  checkProvider(@Param('provider') provider: 'ollama' | 'openai' | 'perplexity') {
    return this.service.checkProvider(provider);
  }

  @Post('ollama/start')
  @ApiOperation({ summary: 'Ollama Docker-Container starten' })
  startOllama() {
    return this.service.startOllama();
  }

  @Post('ollama/stop')
  @ApiOperation({ summary: 'Ollama Docker-Container stoppen' })
  stopOllama() {
    return this.service.stopOllama();
  }
}

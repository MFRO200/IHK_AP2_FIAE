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
  @ApiQuery({ name: 'provider', enum: ['ollama', 'openai'] })
  @ApiQuery({ name: 'model', required: false })
  bewertenPruefung(
    @Param('pruefungId', ParseIntPipe) pruefungId: number,
    @Query('provider') provider: 'ollama' | 'openai' = 'ollama',
    @Query('model') model?: string,
  ) {
    return this.service.bewertenPruefung(pruefungId, provider, model);
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
  checkProvider(@Param('provider') provider: 'ollama' | 'openai') {
    return this.service.checkProvider(provider);
  }
}

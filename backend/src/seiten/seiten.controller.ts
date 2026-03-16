import {
  Controller, Get,
  Param, Query, ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { SeitenService } from './seiten.service';

@ApiTags('Seiten')
@Controller('seiten')
export class SeitenController {
  constructor(private readonly service: SeitenService) {}

  @Get('search')
  @ApiOperation({ summary: 'Volltext-Suche über alle OCR-Seiten (PostgreSQL ts_vector)' })
  @ApiQuery({ name: 'q', required: true, description: 'Suchtext (deutsch)' })
  @ApiQuery({ name: 'limit', required: false, type: Number, description: 'Max. Ergebnisse (default 50)' })
  search(
    @Query('q') q: string,
    @Query('limit') limit?: string,
  ) {
    return this.service.fullTextSearch(q, limit ? parseInt(limit, 10) : 50);
  }

  @Get('dokument/:dokumentId')
  @ApiOperation({ summary: 'Alle Seiten eines Dokuments' })
  findByDokument(@Param('dokumentId', ParseIntPipe) dokumentId: number) {
    return this.service.findByDokument(dokumentId);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelne Seite mit OCR-Text' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }
}

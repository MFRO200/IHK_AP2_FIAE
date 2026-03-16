import {
  Controller, Get, Post, Put, Delete,
  Param, Body, Query, ParseIntPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { SuchbegriffeService } from './suchbegriffe.service';
import { CreateSuchbegriffDto, UpdateSuchbegriffDto } from './dto/suchbegriffe.dto';

@ApiTags('Suchbegriffe')
@Controller('suchbegriffe')
export class SuchbegriffeController {
  constructor(private readonly service: SuchbegriffeService) {}

  @Get()
  @ApiOperation({ summary: 'Alle Suchbegriffe auflisten (optional nach Section filtern)' })
  @ApiQuery({ name: 'section', required: false, enum: ['A', 'B', 'C', 'D', 'X'] })
  findAll(@Query('section') section?: string) {
    return this.service.findAll(section);
  }

  @Get('search')
  @ApiOperation({ summary: 'Suchbegriffe nach Name suchen (case-insensitive)' })
  @ApiQuery({ name: 'q', required: true, description: 'Suchtext' })
  search(@Query('q') q: string) {
    return this.service.search(q);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Einzelner Suchbegriff mit allen Treffern' })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: 'Neuen Suchbegriff anlegen' })
  create(@Body() dto: CreateSuchbegriffDto) {
    return this.service.create(dto);
  }

  @Put(':id')
  @ApiOperation({ summary: 'Suchbegriff aktualisieren' })
  update(
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateSuchbegriffDto,
  ) {
    return this.service.update(id, dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Suchbegriff löschen' })
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.service.remove(id);
  }
}

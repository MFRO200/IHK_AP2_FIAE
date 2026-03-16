import { IsString, IsOptional, IsNumber, IsInt } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreateAntwortDto {
  @ApiProperty({ example: 1, description: 'ID der Prüfung' })
  @IsNumber()
  pruefung_id!: number;

  @ApiProperty({ example: '1a', description: 'Aufgabennummer (z.B. "1a", "2b", "3")' })
  @IsString()
  aufgabe!: string;

  @ApiProperty({ example: 'SELECT * FROM kunden WHERE ort = "Berlin"', description: 'Eigene Lösung / Antworttext' })
  @IsString()
  antwort_text!: string;

  @ApiPropertyOptional({ example: 'Bin mir unsicher bei der WHERE-Klausel' })
  @IsString()
  @IsOptional()
  notiz?: string;

  @ApiPropertyOptional({ example: 8.5 })
  @IsNumber()
  @IsOptional()
  punkte?: number;

  @ApiPropertyOptional({ example: 10 })
  @IsNumber()
  @IsOptional()
  max_punkte?: number;

  @ApiPropertyOptional({ example: 1, description: 'Durchlauf-Nummer (Standard: 1)' })
  @IsInt()
  @IsOptional()
  durchlauf?: number;

  @ApiPropertyOptional({ example: 120, description: 'Bearbeitungsdauer in Sekunden' })
  @IsInt()
  @IsOptional()
  dauer_sekunden?: number;
}

export class UpdateAntwortDto {
  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  antwort_text?: string;

  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  notiz?: string;

  @ApiPropertyOptional()
  @IsNumber()
  @IsOptional()
  punkte?: number;

  @ApiPropertyOptional()
  @IsNumber()
  @IsOptional()
  max_punkte?: number;

  @ApiPropertyOptional()
  @IsInt()
  @IsOptional()
  dauer_sekunden?: number;
}

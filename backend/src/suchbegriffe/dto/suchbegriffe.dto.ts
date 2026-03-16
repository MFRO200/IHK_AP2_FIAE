import { IsString, IsInt, IsOptional } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreateSuchbegriffDto {
  @ApiProperty({ example: 'Pseudocode', description: 'Suchbegriff' })
  @IsString()
  begriff!: string;

  @ApiProperty({ example: 'A', enum: ['A', 'B', 'C', 'D', 'X'], description: 'Score-Section' })
  @IsString()
  section!: string;

  @ApiPropertyOptional({ example: 42 })
  @IsInt()
  @IsOptional()
  treffer_anzahl?: number;
}

export class UpdateSuchbegriffDto {
  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  section?: string;

  @ApiPropertyOptional()
  @IsInt()
  @IsOptional()
  treffer_anzahl?: number;
}

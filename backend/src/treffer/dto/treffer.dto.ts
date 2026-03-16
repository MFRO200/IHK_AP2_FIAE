import { IsString, IsInt, IsOptional } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreateTrefferDto {
  @ApiProperty({ example: 1, description: 'Suchbegriff-ID' })
  @IsInt()
  suchbegriff_id!: number;

  @ApiProperty({ example: 1, description: 'Dokument-ID' })
  @IsInt()
  dokument_id!: number;

  @ApiPropertyOptional({ example: '3, 5, 10', description: 'Seitennummern' })
  @IsString()
  @IsOptional()
  seiten?: string;

  @ApiPropertyOptional({ example: '...Pseudocode für den Algorithmus...' })
  @IsString()
  @IsOptional()
  kontext?: string;
}

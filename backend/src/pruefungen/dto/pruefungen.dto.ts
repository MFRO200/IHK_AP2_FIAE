import { IsInt, IsString, IsOptional } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreatePruefungDto {
  @ApiProperty({ example: 2023, description: 'Prüfungsjahr' })
  @IsInt()
  jahr!: number;

  @ApiProperty({ example: 'Sommer', description: 'Sommer oder Winter' })
  @IsString()
  semester!: string;

  @ApiProperty({ example: 'Sommer 2023' })
  @IsString()
  zeitraum_label!: string;

  @ApiProperty({ example: '2023 Sommer' })
  @IsString()
  ordner_name!: string;
}

export class UpdatePruefungDto {
  @ApiPropertyOptional({ example: 2023 })
  @IsInt()
  @IsOptional()
  jahr?: number;

  @ApiPropertyOptional({ example: 'Winter' })
  @IsString()
  @IsOptional()
  semester?: string;

  @ApiPropertyOptional({ example: 'Winter 2023_24' })
  @IsString()
  @IsOptional()
  zeitraum_label?: string;

  @ApiPropertyOptional({ example: '2023_24 Winter' })
  @IsString()
  @IsOptional()
  ordner_name?: string;
}

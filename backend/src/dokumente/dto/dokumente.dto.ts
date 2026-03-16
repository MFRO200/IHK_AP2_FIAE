import { IsString, IsInt, IsOptional } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreateDokumentDto {
  @ApiProperty({ example: 1, description: 'Prüfungs-ID' })
  @IsInt()
  pruefung_id!: number;

  @ApiProperty({ example: 'AP2_Aufgabe.pdf' })
  @IsString()
  dateiname!: string;

  @ApiProperty({ example: 'AP_IHK_Anwendungsentwicklung/2023 Sommer/AP2_Aufgabe.pdf' })
  @IsString()
  pfad!: string;

  @ApiProperty({ example: 'Aufgabe', enum: ['Aufgabe', 'Lösung', 'Handreichung', 'Belegsatz'] })
  @IsString()
  typ!: string;

  @ApiPropertyOptional({ example: 123456 })
  @IsInt()
  @IsOptional()
  dateigroesse?: number;

  @ApiPropertyOptional({ example: 12 })
  @IsInt()
  @IsOptional()
  seitenanzahl?: number;

  @ApiPropertyOptional({ example: 'GA1', enum: ['GA1', 'GA2', 'WISO', 'AP1', 'Sonstige'] })
  @IsString()
  @IsOptional()
  pruefungsbereich?: string;
}

export class UpdateDokumentDto {
  @ApiPropertyOptional({ example: 1, description: 'Prüfungs-ID (zum Verschieben)' })
  @IsInt()
  @IsOptional()
  pruefung_id?: number;

  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  dateiname?: string;

  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  pfad?: string;

  @ApiPropertyOptional({ enum: ['Aufgabe', 'Lösung', 'Handreichung', 'Belegsatz'] })
  @IsString()
  @IsOptional()
  typ?: string;

  @ApiPropertyOptional({ example: 'GA1', enum: ['GA1', 'GA2', 'WISO', 'AP1', 'Sonstige'] })
  @IsString()
  @IsOptional()
  pruefungsbereich?: string;
}

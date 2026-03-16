import { IsEnum, IsInt, IsOptional, IsString } from 'class-validator';
import { Type } from 'class-transformer';

export class BewertungRequestDto {
  @Type(() => Number)
  @IsInt()
  antwortId: number;

  @IsEnum(['ollama', 'openai'])
  provider: 'ollama' | 'openai';

  @IsOptional()
  @IsString()
  model?: string;

  @IsOptional()
  @IsString()
  image?: string;
}

import { Module } from '@nestjs/common';
import { PsychoAnalyseController } from './psycho-analyse.controller';
import { PsychoAnalyseService } from './psycho-analyse.service';

@Module({
  controllers: [PsychoAnalyseController],
  providers: [PsychoAnalyseService],
})
export class PsychoAnalyseModule {}

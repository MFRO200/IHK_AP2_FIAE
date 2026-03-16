import { Module } from '@nestjs/common';
import { DokumenteController } from './dokumente.controller';
import { DokumenteService } from './dokumente.service';

@Module({
  controllers: [DokumenteController],
  providers: [DokumenteService],
})
export class DokumenteModule {}

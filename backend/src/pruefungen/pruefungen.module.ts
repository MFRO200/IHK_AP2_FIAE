import { Module } from '@nestjs/common';
import { PruefungenController } from './pruefungen.controller';
import { PruefungenService } from './pruefungen.service';

@Module({
  controllers: [PruefungenController],
  providers: [PruefungenService],
})
export class PruefungenModule {}

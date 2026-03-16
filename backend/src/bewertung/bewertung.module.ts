import { Module } from '@nestjs/common';
import { BewertungController } from './bewertung.controller';
import { BewertungService } from './bewertung.service';

@Module({
  controllers: [BewertungController],
  providers: [BewertungService],
})
export class BewertungModule {}

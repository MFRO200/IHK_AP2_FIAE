import { Module } from '@nestjs/common';
import { TrefferController } from './treffer.controller';
import { TrefferService } from './treffer.service';

@Module({
  controllers: [TrefferController],
  providers: [TrefferService],
})
export class TrefferModule {}

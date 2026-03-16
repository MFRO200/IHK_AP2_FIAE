import { Module } from '@nestjs/common';
import { SeitenController } from './seiten.controller';
import { SeitenService } from './seiten.service';

@Module({
  controllers: [SeitenController],
  providers: [SeitenService],
})
export class SeitenModule {}

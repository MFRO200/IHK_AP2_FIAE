import { Module } from '@nestjs/common';
import { AntwortenController } from './antworten.controller';
import { AntwortenService } from './antworten.service';

@Module({
  controllers: [AntwortenController],
  providers: [AntwortenService],
})
export class AntwortenModule {}

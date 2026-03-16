import { Module } from '@nestjs/common';
import { SuchbegriffeController } from './suchbegriffe.controller';
import { SuchbegriffeService } from './suchbegriffe.service';

@Module({
  controllers: [SuchbegriffeController],
  providers: [SuchbegriffeService],
})
export class SuchbegriffeModule {}

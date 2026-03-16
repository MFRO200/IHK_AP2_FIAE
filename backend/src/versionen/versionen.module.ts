import { Module } from '@nestjs/common';
import { VersionenController } from './versionen.controller';
import { VersionenService } from './versionen.service';

@Module({
  controllers: [VersionenController],
  providers: [VersionenService],
  exports: [VersionenService],
})
export class VersionenModule {}

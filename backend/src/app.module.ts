import { Module } from '@nestjs/common';
import { PrismaModule } from './prisma/prisma.module';
import { PruefungenModule } from './pruefungen/pruefungen.module';
import { DokumenteModule } from './dokumente/dokumente.module';
import { SeitenModule } from './seiten/seiten.module';
import { SuchbegriffeModule } from './suchbegriffe/suchbegriffe.module';
import { TrefferModule } from './treffer/treffer.module';
import { VersionenModule } from './versionen/versionen.module';
import { AntwortenModule } from './antworten/antworten.module';
import { PsychoAnalyseModule } from './psycho-analyse/psycho-analyse.module';
import { BewertungModule } from './bewertung/bewertung.module';

@Module({
  imports: [
    PrismaModule,
    PruefungenModule,
    DokumenteModule,
    SeitenModule,
    SuchbegriffeModule,
    TrefferModule,
    VersionenModule,
    AntwortenModule,
    PsychoAnalyseModule,
    BewertungModule,
  ],
})
export class AppModule {}

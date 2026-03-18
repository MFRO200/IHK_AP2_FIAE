import { config } from 'dotenv';
import { resolve } from 'path';

// Lade .env aus dem Projekt-Root (eine Ebene über backend/)
config({ path: resolve(__dirname, '..', '..', '.env') });

import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule } from './app.module';

// BigInt kann nicht von JSON.stringify serialisiert werden → in Number umwandeln
(BigInt.prototype as any).toJSON = function () {
  return Number(this);
};

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);

  // ─── Global prefix ───
  app.setGlobalPrefix('api');

  // ─── CORS ───
  app.enableCors();

  // ─── Validation ───
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      transformOptions: { enableImplicitConversion: true },
    }),
  );

  // ─── Swagger ───
  const config = new DocumentBuilder()
    .setTitle('IHK AP2 FIAE API')
    .setDescription(
      'REST-API für IHK-Abschlussprüfungen: Prüfungen, Dokumente, OCR-Seiten, Suchbegriffe & Treffer',
    )
    .setVersion('1.0')
    .addTag('Prüfungen', 'Prüfungszeiträume (Sommer/Winter)')
    .addTag('Dokumente', 'PDFs: Aufgabe, Lösung, Handreichung')
    .addTag('Seiten', 'OCR-Text pro Seite + Volltext-Suche')
    .addTag('Suchbegriffe', 'Score-Tabelle Begriffe (A/B/C/D/X)')
    .addTag('Treffer', 'Welcher Begriff in welchem Dokument')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document);

  const port = process.env.PORT ?? 3000;
  await app.listen(port);
  console.log(`\n\u{1F680}  API:     http://localhost:${port}/api`);
  console.log(`\u{1F4D6}  Swagger: http://localhost:${port}/api/docs\n`);
}

bootstrap();

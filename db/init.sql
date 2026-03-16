-- ============================================================
-- IHK AP2 FIAE – Datenbankschema
-- ============================================================

-- Prüfungszeiträume (z.B. "Sommer 2018", "Winter 2018_19")
CREATE TABLE IF NOT EXISTS pruefungen (
    id              SERIAL PRIMARY KEY,
    jahr            INTEGER      NOT NULL,          -- z.B. 2018
    semester        VARCHAR(10)  NOT NULL,           -- 'Sommer' oder 'Winter'
    zeitraum_label  VARCHAR(50)  NOT NULL UNIQUE,    -- z.B. 'Sommer 2018', 'Winter 2018_19'
    ordner_name     VARCHAR(100) NOT NULL            -- z.B. '2018 Sommer', '2018_19 Winter'
);

-- Dokumente (PDFs mit OCR-Text)
CREATE TABLE IF NOT EXISTS dokumente (
    id              SERIAL PRIMARY KEY,
    pruefung_id     INTEGER      REFERENCES pruefungen(id) ON DELETE CASCADE,
    dateiname       VARCHAR(500) NOT NULL,
    pfad            TEXT         NOT NULL,           -- relativer Pfad ab Projektroot
    typ             VARCHAR(20)  NOT NULL             -- 'Aufgabe', 'Lösung', 'Handreichung'
                    CHECK (typ IN ('Aufgabe', 'Lösung', 'Handreichung')),
    dateigroesse    BIGINT,
    seitenanzahl    INTEGER      NOT NULL DEFAULT 0,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- OCR-Text pro Seite (für granulare Suche)
CREATE TABLE IF NOT EXISTS seiten (
    id              SERIAL PRIMARY KEY,
    dokument_id     INTEGER      NOT NULL REFERENCES dokumente(id) ON DELETE CASCADE,
    seiten_nr       INTEGER      NOT NULL,           -- 1-basiert
    ocr_text        TEXT         NOT NULL,
    UNIQUE(dokument_id, seiten_nr)
);

-- Suchbegriffe aus der Score-Tabelle
CREATE TABLE IF NOT EXISTS suchbegriffe (
    id              SERIAL PRIMARY KEY,
    begriff         VARCHAR(200) NOT NULL UNIQUE,
    section         CHAR(1)      NOT NULL             -- 'A', 'B', 'C', 'D', 'X' (X=nicht in Score-Tabelle)
                    CHECK (section IN ('A', 'B', 'C', 'D', 'X')),
    treffer_anzahl  INTEGER      NOT NULL DEFAULT 0   -- Anzahl Dokumente mit Treffer
);

-- Treffer: welcher Suchbegriff in welchem Dokument auf welchen Seiten
CREATE TABLE IF NOT EXISTS treffer (
    id              SERIAL PRIMARY KEY,
    suchbegriff_id  INTEGER      NOT NULL REFERENCES suchbegriffe(id) ON DELETE CASCADE,
    dokument_id     INTEGER      NOT NULL REFERENCES dokumente(id) ON DELETE CASCADE,
    seiten          TEXT,                              -- z.B. '3, 5, 10'
    kontext         TEXT,                              -- Kontext-Snippet
    UNIQUE(suchbegriff_id, dokument_id)
);

-- Dokument-Versionen (Original + bearbeitete Kopien)
CREATE TABLE IF NOT EXISTS dokument_versionen (
    id              SERIAL PRIMARY KEY,
    dokument_id     INTEGER      NOT NULL REFERENCES dokumente(id) ON DELETE CASCADE,
    version_nr      INTEGER      NOT NULL DEFAULT 1,
    label           VARCHAR(200) NOT NULL DEFAULT 'Original',
    dateiname       VARCHAR(500) NOT NULL,
    storage_pfad    TEXT         NOT NULL,           -- Pfad in storage/
    dateigroesse    BIGINT,
    kommentar       TEXT,
    erstellt_am     TIMESTAMP    NOT NULL DEFAULT NOW(),
    UNIQUE(dokument_id, version_nr)
);

-- ============================================================
-- Indizes für performante Abfragen
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_dokumente_pruefung    ON dokumente(pruefung_id);
CREATE INDEX IF NOT EXISTS idx_dokumente_typ         ON dokumente(typ);
CREATE INDEX IF NOT EXISTS idx_seiten_dokument       ON seiten(dokument_id);
CREATE INDEX IF NOT EXISTS idx_treffer_suchbegriff   ON treffer(suchbegriff_id);
CREATE INDEX IF NOT EXISTS idx_treffer_dokument      ON treffer(dokument_id);
CREATE INDEX IF NOT EXISTS idx_suchbegriffe_section  ON suchbegriffe(section);
CREATE INDEX IF NOT EXISTS idx_versionen_dokument    ON dokument_versionen(dokument_id);

-- Volltextsuche auf OCR-Text
CREATE INDEX IF NOT EXISTS idx_seiten_ocr_gin
    ON seiten USING gin(to_tsvector('german', ocr_text));

-- ============================================================
-- Hilfreiche Views
-- ============================================================

-- Dokument-Übersicht mit Prüfungszeitraum
CREATE OR REPLACE VIEW v_dokumente_komplett AS
SELECT
    d.id,
    p.zeitraum_label   AS pruefung,
    p.jahr,
    p.semester,
    d.typ,
    d.dateiname,
    d.pfad,
    d.seitenanzahl,
    d.dateigroesse
FROM dokumente d
JOIN pruefungen p ON d.pruefung_id = p.id
ORDER BY p.jahr, p.semester, d.typ;

-- Treffer mit allen Details
CREATE OR REPLACE VIEW v_treffer_komplett AS
SELECT
    s.begriff,
    s.section,
    p.zeitraum_label   AS pruefung,
    d.typ              AS dokument_typ,
    d.dateiname,
    t.seiten,
    t.kontext
FROM treffer t
JOIN suchbegriffe s ON t.suchbegriff_id = s.id
JOIN dokumente d    ON t.dokument_id = d.id
JOIN pruefungen p   ON d.pruefung_id = p.id
ORDER BY s.section, s.treffer_anzahl DESC, p.jahr, p.semester;

-- Aufgabe + Lösung pro Prüfung (Side-by-Side Basis)
CREATE OR REPLACE VIEW v_aufgabe_loesung AS
SELECT
    p.zeitraum_label   AS pruefung,
    p.jahr,
    p.semester,
    MAX(CASE WHEN d.typ = 'Aufgabe' THEN d.dateiname END)       AS aufgabe_pdf,
    MAX(CASE WHEN d.typ = 'Lösung' THEN d.dateiname END)        AS loesung_pdf,
    MAX(CASE WHEN d.typ = 'Handreichung' THEN d.dateiname END)  AS handreichung_pdf
FROM pruefungen p
LEFT JOIN dokumente d ON d.pruefung_id = p.id
GROUP BY p.id, p.zeitraum_label, p.jahr, p.semester
ORDER BY p.jahr, p.semester;

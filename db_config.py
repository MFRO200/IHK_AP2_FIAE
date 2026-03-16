"""
Zentrale Datenbank-Konfiguration.
Liest Credentials aus Umgebungsvariablen oder .env-Datei.
Keine hardcoded Secrets im Code.
"""
import os
from pathlib import Path

# .env laden falls vorhanden (ohne externe Abhängigkeit)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# Connection URL (PostgreSQL)
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
        user=os.environ.get("POSTGRES_USER", "ihk"),
        pw=os.environ.get("POSTGRES_PASSWORD", ""),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", "15432"),
        db=os.environ.get("POSTGRES_DB", "ihk_ap2"),
    ),
)

# Connection-Dict (für psycopg2-Keyword-Args)
DB_CONF = dict(
    host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.environ.get("POSTGRES_PORT", "15432")),
    dbname=os.environ.get("POSTGRES_DB", "ihk_ap2"),
    user=os.environ.get("POSTGRES_USER", "ihk"),
    password=os.environ.get("POSTGRES_PASSWORD", ""),
)

# Connection-String (psycopg key=value Format)
DB_DSN = " ".join(f"{k}={v}" for k, v in DB_CONF.items())

import os
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parent / ".env")


class Config:
    """Configuración base de la aplicación."""

    # Firma de los JWT (HS256). Mínimo 32 caracteres; nunca se sube al repositorio.
    SECRET_KEY = os.getenv("SECRET_KEY")
    # Segundos de validez de un token (claim "exp").
    AUTH_TOKEN_MAX_AGE = int(os.getenv("AUTH_TOKEN_MAX_AGE", "3600"))

    SQLALCHEMY_DATABASE_URI = URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "prestamos_activos"),
        query={"charset": "utf8mb4"},
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "connect_args": {"connect_timeout": 5},
    }

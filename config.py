import os
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parent / ".env")


class Config:
    """Configuración base de la aplicación."""

    SECRET_KEY = os.getenv("SECRET_KEY")
    AUTH_TOKEN_MAX_AGE = int(os.getenv("AUTH_TOKEN_MAX_AGE", "3600"))
    API_OPERATOR_IDS = tuple(int(value.strip()) for value in os.getenv("API_OPERATOR_IDS", "").split(",") if value.strip())

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

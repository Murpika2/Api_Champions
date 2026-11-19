"""Configuración de la aplicación.

Todos los secretos y direcciones se leen de variables de entorno (archivo .env
en desarrollo). Nunca se escriben claves reales en el código (RF08 / NU03).
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")


def _int(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"La variable {name} debe ser un número entero") from exc


def load_config():
    """Devuelve la configuración leída del entorno."""
    db_path = os.getenv("DATABASE_PATH") or os.path.join(BASE_DIR, "data", "champions.db")
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

    return {
        # Firma de los JWT. Obligatoria y de al menos 32 caracteres.
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "JWT_ACCESS_TOKEN_EXPIRES": timedelta(minutes=_int("JWT_EXPIRES_MINUTES", 60)),
        "JWT_TOKEN_LOCATION": ["headers"],
        # Base de datos SQLite (en la nube debe estar en un volumen persistente)
        "DATABASE_PATH": os.path.abspath(db_path),
        # Usuarios iniciales (solo se crean si la tabla users está vacía)
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD"),
        "VIEWER_USERNAME": os.getenv("VIEWER_USERNAME", "invitado"),
        "VIEWER_PASSWORD": os.getenv("VIEWER_PASSWORD"),
        # Datos de ejemplo (equipos y jugadores) cuando la base está vacía
        "SEED_DEMO_DATA": _bool("SEED_DEMO_DATA", True),
        # Orígenes autorizados para CORS (lista separada por comas)
        "CORS_ORIGINS": origins,
        # Dirección base de la API que usará la interfaz web
        "FRONTEND_API_BASE": os.getenv("FRONTEND_API_BASE", "/api"),
        # Cupos de clasificación (0 = automático: la mitad de los equipos)
        "QUALIFICATION_SPOTS": _int("QUALIFICATION_SPOTS", 0),
        "JSON_SORT_KEYS": False,
    }

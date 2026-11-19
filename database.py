"""Acceso a la base de datos SQLite (RF07).

- Una conexión por petición (se cierra al terminar la petición).
- Llaves foráneas activadas.
- Todas las consultas del proyecto usan parámetros "?" (RF08).
"""
import os
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('admin', 'viewer')),
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teams (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    country    TEXT    NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_teams_name ON teams (name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS matches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team_id INTEGER NOT NULL REFERENCES teams (id),
    away_team_id INTEGER NOT NULL REFERENCES teams (id),
    home_goals   INTEGER NOT NULL CHECK (home_goals BETWEEN 0 AND 99),
    away_goals   INTEGER NOT NULL CHECK (away_goals BETWEEN 0 AND 99),
    created_by   TEXT,
    played_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (home_team_id <> away_team_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_matches_pair ON matches (home_team_id, away_team_id);

CREATE TABLE IF NOT EXISTS players (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    team_id    INTEGER NOT NULL REFERENCES teams (id),
    goals      INTEGER NOT NULL DEFAULT 0 CHECK (goals >= 0),
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_players_team_name ON players (team_id, name COLLATE NOCASE);
"""

DEMO_TEAMS = [
    ("Real Madrid", "España"),
    ("Manchester City", "Inglaterra"),
    ("FC Barcelona", "España"),
    ("Bayern Múnich", "Alemania"),
    ("Liverpool", "Inglaterra"),
    ("Paris Saint-Germain", "Francia"),
    ("Inter de Milán", "Italia"),
    ("Borussia Dortmund", "Alemania"),
]

DEMO_PLAYERS = [
    ("Kylian Mbappé", "Real Madrid", 5),
    ("Erling Haaland", "Manchester City", 6),
    ("Robert Lewandowski", "FC Barcelona", 4),
    ("Harry Kane", "Bayern Múnich", 5),
    ("Mohamed Salah", "Liverpool", 3),
    ("Ousmane Dembélé", "Paris Saint-Germain", 2),
    ("Lautaro Martínez", "Inter de Milán", 4),
    ("Serhou Guirassy", "Borussia Dortmund", 3),
]


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Conexión de la petición actual."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def create_user(conn, username, password, role):
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), role),
    )


def init_db(app):
    """Crea las tablas y, si la base está vacía, los usuarios y datos iniciales."""
    path = app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)

        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            admin_pw = app.config.get("ADMIN_PASSWORD")
            if not admin_pw:
                raise RuntimeError(
                    "No hay usuarios en la base y falta ADMIN_PASSWORD en el .env. "
                    "Defínela para crear el administrador inicial."
                )
            create_user(conn, app.config["ADMIN_USERNAME"], admin_pw, "admin")
            if app.config.get("VIEWER_PASSWORD"):
                create_user(conn, app.config["VIEWER_USERNAME"], app.config["VIEWER_PASSWORD"], "viewer")

        if app.config.get("SEED_DEMO_DATA") and conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0:
            conn.executemany("INSERT INTO teams (name, country) VALUES (?, ?)", DEMO_TEAMS)
            for name, team, goals in DEMO_PLAYERS:
                conn.execute(
                    "INSERT INTO players (name, team_id, goals) "
                    "SELECT ?, id, ? FROM teams WHERE name = ?",
                    (name, goals, team),
                )
        conn.commit()
    finally:
        conn.close()

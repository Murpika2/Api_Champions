"""API Champions: gestión de un torneo de fútbol tipo liga + eliminatorias.

Ejecutar en desarrollo:  python app.py
Ejecutar en producción:  gunicorn wsgi:app
"""
import logging
import os
import sqlite3
from functools import wraps

import click
from flask import Blueprint, Flask, current_app, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    current_user,
    jwt_required,
    verify_jwt_in_request,
)
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

import services
from config import load_config
from database import close_db, connect, create_user, get_db, init_db
from validators import ApiError, Validator, json_body, query_bool, query_int, query_text

log = logging.getLogger("api_champions")
api = Blueprint("api", __name__, url_prefix="/api")
jwt = JWTManager()


# ---------------------------------------------------------------------------
# Respuestas JSON consistentes (RF06)
#   Éxito: {"status": "success", "message": ..., "data": ...}
#   Error: {"status": "error",   "error": ...,   "details": ...}
# ---------------------------------------------------------------------------
def ok(data=None, message=None, status=200, **meta):
    body = {"status": "success", "message": message, "data": data}
    body.update(meta)
    return jsonify(body), status


def error_response(status, message, details=None, code=None):
    body = {"status": "error", "error": message}
    if details:
        body["details"] = details
    if code:
        body["code"] = code
    return jsonify(body), status


# ---------------------------------------------------------------------------
# Autenticación y permisos (RF03 / RF04)
# ---------------------------------------------------------------------------
@jwt.user_lookup_loader
def _load_user(_header, payload):
    """Cada petición protegida comprueba que el usuario del token siga existiendo."""
    row = get_db().execute(
        "SELECT id, username, role FROM users WHERE id = ?", (int(payload["sub"]),)
    ).fetchone()
    return dict(row) if row else None


@jwt.user_lookup_error_loader
def _user_not_found(_header, _payload):
    return error_response(401, "El usuario del token ya no existe. Inicia sesión de nuevo.", code="invalid_token")


@jwt.unauthorized_loader
def _missing_token(_reason):
    return error_response(401, "Falta el token de acceso. Inicia sesión.", code="missing_token")


@jwt.invalid_token_loader
def _invalid_token(_reason):
    return error_response(401, "Token inválido o alterado. Inicia sesión de nuevo.", code="invalid_token")


@jwt.expired_token_loader
def _expired_token(_header, _payload):
    return error_response(401, "Tu sesión expiró. Inicia sesión de nuevo.", code="token_expired")


def admin_required(fn):
    """Exige token válido y rol 'admin' (el rol se lee de la base, no del cliente)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if current_user["role"] != "admin":
            raise ApiError(403, "No tienes permisos para esta acción (requiere rol administrador)")
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Utilidades de datos
# ---------------------------------------------------------------------------
def _team_or_404(team_id):
    row = get_db().execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
    if row is None:
        raise ApiError(404, f"No existe un equipo con id {team_id}")
    return _team_dict(row)


def _team_dict(row):
    t = dict(row)
    t["active"] = bool(t["active"])
    return t


def _active_teams():
    rows = get_db().execute("SELECT * FROM teams WHERE active = 1 ORDER BY id").fetchall()
    return [_team_dict(r) for r in rows]


def _all_matches():
    rows = get_db().execute(
        "SELECT id, home_team_id, away_team_id, home_goals, away_goals FROM matches"
    ).fetchall()
    return [dict(r) for r in rows]


def _stats_for(team_ids):
    return services.compute_stats(team_ids, _all_matches())


def _with_stats(team, stats):
    return {**team, **stats.get(team["id"], services.empty_stats())}


def _spots(n_teams, requested=None):
    if requested is not None:
        if requested >= n_teams:
            raise ApiError(400, "Datos inválidos", {"spots": "Los cupos deben ser menores que el número de equipos activos"})
        return requested
    return services.default_spots(n_teams, current_app.config["QUALIFICATION_SPOTS"])


def _like(value):
    """Escapa comodines de LIKE para que el usuario no los inyecte."""
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------------------------------------------------------------------------
# Salud y autenticación
# ---------------------------------------------------------------------------
@api.get("/health")
def health():
    teams = get_db().execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    return ok({"service": "api-champions", "database": "ok", "teams": teams})


@api.post("/auth/login")
def login():
    data = json_body()
    v = Validator(data)
    username = v.text("username", max_len=40, label="usuario")
    password = v.text("password", max_len=128, label="contraseña")
    v.check()

    user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], data["password"]):
        # Mismo mensaje para usuario o contraseña: no revela cuál falló
        raise ApiError(401, "Usuario o contraseña incorrectos")

    token = create_access_token(identity=str(user["id"]), additional_claims={"role": user["role"]})
    expires = int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())
    return ok(
        {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": expires,
            "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
        },
        "Inicio de sesión exitoso",
    )


@api.get("/auth/me")
@jwt_required()
def me():
    return ok(dict(current_user))


# ---------------------------------------------------------------------------
# CRUD de equipos (RF01) + búsqueda (RF02)
# ---------------------------------------------------------------------------
@api.get("/teams")
def list_teams():
    name = query_text("name")
    country = query_text("country", max_len=40)
    include_inactive = query_bool("include_inactive")

    sql = "SELECT * FROM teams WHERE 1 = 1"
    params = []
    if not include_inactive:
        sql += " AND active = 1"
    if name:
        sql += " AND name LIKE ? ESCAPE '\\'"
        params.append(_like(name))
    if country:
        sql += " AND country LIKE ? ESCAPE '\\'"
        params.append(_like(country))
    sql += " ORDER BY name COLLATE NOCASE"

    teams = [_team_dict(r) for r in get_db().execute(sql, params).fetchall()]
    stats = _stats_for([t["id"] for t in teams])
    data = [_with_stats(t, stats) for t in teams]
    message = None if data else "No se encontraron equipos con esos criterios"
    return ok(data, message, count=len(data), filters={"name": name, "country": country, "include_inactive": include_inactive})


@api.get("/teams/<int:team_id>")
def get_team(team_id):
    team = _team_or_404(team_id)
    stats = _stats_for([team_id])
    players = get_db().execute(
        "SELECT id, name, goals FROM players WHERE team_id = ? ORDER BY goals DESC, name", (team_id,)
    ).fetchall()
    return ok({**_with_stats(team, stats), "players": [dict(p) for p in players]})


def _validate_team(data, partial=False):
    v = Validator(data)
    name = v.text("name", min_len=2, max_len=60, required=not partial, pattern=Validator.NAME_RE, label="nombre")
    country = v.text("country", min_len=3, max_len=40, required=not partial, pattern=Validator.COUNTRY_RE, label="país")
    if name is not None and not any(c.isalpha() for c in name):
        v.add("name", "'nombre' debe contener al menos una letra")
    if partial and "name" not in data and "country" not in data:
        v.add("body", "Envía al menos 'name' o 'country' para actualizar")
    v.check()
    return name, country


def _ensure_unique_name(name, exclude_id=None):
    row = get_db().execute(
        "SELECT id, active FROM teams WHERE name = ? COLLATE NOCASE AND id IS NOT ?", (name, exclude_id)
    ).fetchone()
    if row:
        extra = " (está desactivado; puedes reactivarlo)" if not row["active"] else ""
        raise ApiError(409, f"Ya existe un equipo llamado '{name}'{extra}", {"existing_id": row["id"]})


@api.post("/teams")
@admin_required
def create_team():
    name, country = _validate_team(json_body())
    _ensure_unique_name(name)
    db = get_db()
    cur = db.execute("INSERT INTO teams (name, country) VALUES (?, ?)", (name, country))
    db.commit()
    team = _team_or_404(cur.lastrowid)
    return ok(_with_stats(team, {}), f"Equipo '{name}' creado", 201)


@api.put("/teams/<int:team_id>")
@admin_required
def update_team(team_id):
    data = json_body()
    team = _team_or_404(team_id)
    name, country = _validate_team(data, partial=True)
    name = name or team["name"]
    country = country or team["country"]
    _ensure_unique_name(name, exclude_id=team_id)
    db = get_db()
    db.execute("UPDATE teams SET name = ?, country = ? WHERE id = ?", (name, country, team_id))
    db.commit()
    updated = _team_or_404(team_id)
    return ok(_with_stats(updated, _stats_for([team_id])), "Equipo actualizado")


@api.delete("/teams/<int:team_id>")
@admin_required
def deactivate_team(team_id):
    """Desactivación (borrado lógico).

    Regla de negocio: un equipo no se borra físicamente porque sus partidos
    forman parte de la historia del torneo y afectan los puntos de los rivales.
    Un equipo desactivado no aparece en listados ni en la tabla, no puede
    jugar partidos nuevos y sus jugadores salen de la Bota de Oro.
    """
    team = _team_or_404(team_id)
    if not team["active"]:
        raise ApiError(409, f"El equipo '{team['name']}' ya está desactivado")
    db = get_db()
    db.execute("UPDATE teams SET active = 0 WHERE id = ?", (team_id,))
    db.commit()
    return ok(_team_or_404(team_id), f"Equipo '{team['name']}' desactivado")


@api.patch("/teams/<int:team_id>/activate")
@admin_required
def activate_team(team_id):
    team = _team_or_404(team_id)
    if team["active"]:
        raise ApiError(409, f"El equipo '{team['name']}' ya está activo")
    db = get_db()
    db.execute("UPDATE teams SET active = 1 WHERE id = ?", (team_id,))
    db.commit()
    return ok(_team_or_404(team_id), f"Equipo '{team['name']}' reactivado")


# ---------------------------------------------------------------------------
# Partidos
# ---------------------------------------------------------------------------
MATCH_SQL = """
SELECT m.id, m.home_team_id, h.name AS home_team, m.away_team_id, a.name AS away_team,
       m.home_goals, m.away_goals, m.played_at, m.created_by
FROM matches m
JOIN teams h ON h.id = m.home_team_id
JOIN teams a ON a.id = m.away_team_id
"""


def _match_dict(row):
    m = dict(row)
    m["score"] = f"{m['home_goals']} - {m['away_goals']}"
    return m


@api.get("/matches")
def list_matches():
    team_id = query_int("team_id", min_value=1, max_value=10**9)
    if team_id:
        _team_or_404(team_id)
        rows = get_db().execute(
            MATCH_SQL + " WHERE m.home_team_id = ? OR m.away_team_id = ? ORDER BY m.id DESC", (team_id, team_id)
        ).fetchall()
    else:
        rows = get_db().execute(MATCH_SQL + " ORDER BY m.id DESC").fetchall()
    data = [_match_dict(r) for r in rows]
    return ok(data, None if data else "Todavía no hay partidos registrados", count=len(data))


@api.post("/matches")
@admin_required
def register_match():
    v = Validator(json_body())
    home_id = v.integer("home_team_id", min_value=1, label="equipo local")
    away_id = v.integer("away_team_id", min_value=1, label="equipo visitante")
    home_goals = v.integer("home_goals", min_value=0, max_value=99, label="goles local")
    away_goals = v.integer("away_goals", min_value=0, max_value=99, label="goles visitante")
    if home_id is not None and home_id == away_id:
        v.add("away_team_id", "Un equipo no puede jugar contra sí mismo")
    v.check()

    home, away = _team_or_404(home_id), _team_or_404(away_id)
    for t in (home, away):
        if not t["active"]:
            raise ApiError(409, f"'{t['name']}' está desactivado y no puede jugar partidos")

    db = get_db()
    exists = db.execute(
        "SELECT id FROM matches WHERE home_team_id = ? AND away_team_id = ?", (home_id, away_id)
    ).fetchone()
    if exists:
        raise ApiError(
            409,
            f"Ya se jugó {home['name']} (local) vs {away['name']}. "
            "Cada pareja juega una vez de local y otra de visitante.",
            {"existing_match_id": exists["id"]},
        )

    before = {r["id"]: r["position"] for r in _standings_rows()}
    cur = db.execute(
        "INSERT INTO matches (home_team_id, away_team_id, home_goals, away_goals, created_by) VALUES (?, ?, ?, ?, ?)",
        (home_id, away_id, home_goals, away_goals, current_user["username"]),
    )
    db.commit()
    match = _match_dict(db.execute(MATCH_SQL + " WHERE m.id = ?", (cur.lastrowid,)).fetchone())

    # Efecto del partido en la tabla (antes y después)
    after = {r["id"]: r for r in _standings_rows()}
    effects = [
        {
            "team_id": tid,
            "team": after[tid]["name"],
            "points": after[tid]["points"],
            "position_before": before.get(tid),
            "position_after": after[tid]["position"],
        }
        for tid in (home_id, away_id)
    ]
    return ok({"match": match, "effects": effects}, "Partido registrado; la tabla se actualizó", 201)


@api.delete("/matches/<int:match_id>")
@admin_required
def delete_match(match_id):
    """Anula un partido mal registrado. La tabla se recalcula sola."""
    db = get_db()
    row = db.execute(MATCH_SQL + " WHERE m.id = ?", (match_id,)).fetchone()
    if row is None:
        raise ApiError(404, f"No existe un partido con id {match_id}")
    db.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    db.commit()
    return ok(_match_dict(row), "Partido anulado; la tabla se recalculó")


# ---------------------------------------------------------------------------
# FUNCIÓN ESPECIAL (RF10) – Motor del torneo
# ---------------------------------------------------------------------------
def _standings_rows():
    teams = _active_teams()
    return services.sort_standings(teams, services.compute_stats([t["id"] for t in teams], _all_matches()))


@api.get("/standings")
def standings():
    """Tabla de posiciones calculada a partir de los partidos + estado de clasificación."""
    teams = _active_teams()
    matches = _all_matches()
    rows = services.sort_standings(teams, services.compute_stats([t["id"] for t in teams], matches))
    spots = _spots(len(rows)) if len(rows) >= 2 else 0
    for r in rows:
        r["zone"] = "clasifica" if r["position"] <= spots else "eliminado"
        if spots:
            q = services.qualification(r["id"], teams, matches, spots)
            r["qualification_status"] = q["status"]
            r["matches_remaining"] = q["matches_remaining"]
    total = get_db().execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    return ok(rows, None if rows else "No hay equipos activos", total_matches_played=total, qualification_spots=spots)


@api.get("/teams/<int:team_id>/qualification")
def qualification(team_id):
    """Calculadora matemática: ¿qué necesita un equipo para clasificar?"""
    team = _team_or_404(team_id)
    if not team["active"]:
        raise ApiError(409, f"'{team['name']}' está desactivado y no participa en la clasificación")
    teams = _active_teams()
    if len(teams) < 2:
        raise ApiError(409, "Se necesitan al menos 2 equipos activos")
    requested = query_int("spots", min_value=1, max_value=1000)
    spots = _spots(len(teams), requested)
    result = services.qualification(team_id, teams, _all_matches(), spots)
    position = next(r["position"] for r in _standings_rows() if r["id"] == team_id)
    return ok({"team": team["name"], "position": position, **result})


@api.get("/schedule")
def schedule():
    """Genera el calendario todos contra todos (no modifica datos)."""
    double_round = query_bool("double_round", True)
    only_pending = query_bool("only_pending", False)
    teams = _active_teams()
    if len(teams) < 2:
        raise ApiError(409, "Se necesitan al menos 2 equipos activos para generar el calendario")
    rounds = services.generate_fixture(teams, _all_matches(), double_round, only_pending)
    total = sum(len(r["matches"]) for r in rounds)
    msg = f"Calendario con {len(rounds)} jornadas y {total} partidos" if total else "No quedan partidos pendientes"
    return ok(rounds, msg, total_rounds=len(rounds), total_matches=total)


@api.post("/knockout/simulate")
@jwt_required()
def knockout():
    """Simula una eliminatoria ida y vuelta. No guarda nada en la base."""
    v = Validator(json_body())
    t1_id = v.integer("team1_id", min_value=1, label="equipo 1")
    t2_id = v.integer("team2_id", min_value=1, label="equipo 2")
    seed = v.integer("seed", min_value=0, max_value=10**9, required=False)
    if t1_id is not None and t1_id == t2_id:
        v.add("team2_id", "Elige dos equipos diferentes")
    v.check()
    t1, t2 = _team_or_404(t1_id), _team_or_404(t2_id)
    for t in (t1, t2):
        if not t["active"]:
            raise ApiError(409, f"'{t['name']}' está desactivado")
    result = services.simulate_knockout(t1, t2, _stats_for([t1_id, t2_id]), seed)
    return ok(result, f"Clasifica {result['winner']['name']}")


# ---- Bota de Oro (jugadores y goleadores) ----
PLAYER_SQL = """
SELECT p.id, p.name, p.goals, p.team_id, t.name AS team_name, t.country
FROM players p JOIN teams t ON t.id = p.team_id
"""


def _player_or_404(player_id):
    row = get_db().execute(PLAYER_SQL + " WHERE p.id = ?", (player_id,)).fetchone()
    if row is None:
        raise ApiError(404, f"No existe un jugador con id {player_id}")
    return dict(row)


@api.get("/top-scorers")
def top_scorers():
    limit = query_int("limit", min_value=1, max_value=50, default=10)
    rows = get_db().execute(
        PLAYER_SQL + " WHERE t.active = 1 ORDER BY p.goals DESC, p.name COLLATE NOCASE LIMIT ?", (limit,)
    ).fetchall()
    data = [{**dict(r), "rank": i} for i, r in enumerate(rows, start=1)]
    return ok(data, None if data else "No hay goleadores registrados", count=len(data))


@api.get("/players")
def list_players():
    team_id = query_int("team_id", min_value=1, max_value=10**9)
    if team_id:
        _team_or_404(team_id)
        rows = get_db().execute(PLAYER_SQL + " WHERE p.team_id = ? ORDER BY p.name", (team_id,)).fetchall()
    else:
        rows = get_db().execute(PLAYER_SQL + " WHERE t.active = 1 ORDER BY t.name, p.name").fetchall()
    data = [dict(r) for r in rows]
    return ok(data, None if data else "No hay jugadores", count=len(data))


@api.post("/players")
@admin_required
def create_player():
    v = Validator(json_body())
    name = v.text("name", min_len=2, max_len=60, pattern=Validator.NAME_RE, label="nombre")
    team_id = v.integer("team_id", min_value=1, label="equipo")
    goals = v.integer("goals", min_value=0, max_value=99, required=False, default=0, label="goles")
    v.check()
    team = _team_or_404(team_id)
    if not team["active"]:
        raise ApiError(409, f"'{team['name']}' está desactivado; no se le pueden agregar jugadores")
    db = get_db()
    try:
        cur = db.execute("INSERT INTO players (name, team_id, goals) VALUES (?, ?, ?)", (name, team_id, goals))
    except sqlite3.IntegrityError:
        raise ApiError(409, f"'{name}' ya está registrado en {team['name']}")
    db.commit()
    return ok(_player_or_404(cur.lastrowid), f"Jugador '{name}' registrado", 201)


@api.patch("/players/<int:player_id>/goals")
@admin_required
def add_goals(player_id):
    """Suma (o corrige con números negativos) goles de un jugador."""
    v = Validator(json_body())
    delta = v.integer("goals", min_value=-10, max_value=10, label="goles")
    if delta == 0:
        v.add("goals", "'goles' no puede ser 0")
    v.check()
    player = _player_or_404(player_id)
    new_total = player["goals"] + delta
    if new_total < 0:
        raise ApiError(409, f"{player['name']} tiene {player['goals']} goles; no puede quedar en negativo")
    db = get_db()
    db.execute("UPDATE players SET goals = ? WHERE id = ?", (new_total, player_id))
    db.commit()
    return ok(_player_or_404(player_id), f"Goles de {player['name']}: {new_total}")


@api.delete("/players/<int:player_id>")
@admin_required
def delete_player(player_id):
    player = _player_or_404(player_id)
    db = get_db()
    db.execute("DELETE FROM players WHERE id = ?", (player_id,))
    db.commit()
    return ok(player, f"Jugador '{player['name']}' eliminado")


# ---------------------------------------------------------------------------
# Fábrica de la aplicación
# ---------------------------------------------------------------------------
def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(load_config())
    if test_config:
        app.config.update(test_config)

    secret = app.config.get("JWT_SECRET_KEY")
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "Falta JWT_SECRET_KEY (mínimo 32 caracteres). Copia .env.example a .env y define una clave."
        )

    app.json.sort_keys = False
    jwt.init_app(app)
    if app.config["CORS_ORIGINS"]:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    app.register_blueprint(api)
    app.teardown_appcontext(close_db)

    @app.get("/")
    def index():
        return render_template("index.html", api_base=app.config["FRONTEND_API_BASE"])

    @app.errorhandler(ApiError)
    def _api_error(err):
        return error_response(err.status, err.message, err.details)

    @app.errorhandler(HTTPException)
    def _http_error(err):
        messages = {
            404: "Recurso no encontrado",
            405: "Método no permitido para esta ruta",
            415: "El cuerpo debe enviarse como JSON",
        }
        return error_response(err.code, messages.get(err.code, err.description))

    @app.errorhandler(Exception)
    def _unexpected(err):
        log.exception("Error no controlado: %s", err)
        return error_response(500, "Error interno del servidor")

    @app.cli.command("init-db")
    def init_db_command():
        """Crea las tablas y los datos iniciales."""
        init_db(app)
        click.echo(f"Base de datos lista en {app.config['DATABASE_PATH']}")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.option("--role", type=click.Choice(["admin", "viewer"]), default="viewer")
    @click.password_option()
    def create_user_command(username, role, password):
        """Crea un usuario (la contraseña se guarda con hash)."""
        conn = connect(app.config["DATABASE_PATH"])
        try:
            create_user(conn, username, password, role)
            conn.commit()
            click.echo(f"Usuario '{username}' creado con rol {role}")
        except sqlite3.IntegrityError:
            click.echo(f"El usuario '{username}' ya existe")
        finally:
            conn.close()

    @app.cli.command("demo-matches")
    def demo_matches_command():
        """Registra la primera jornada del calendario con resultados aleatorios."""
        import random

        conn = connect(app.config["DATABASE_PATH"])
        try:
            teams = [dict(r) for r in conn.execute("SELECT id, name FROM teams WHERE active = 1")]
            played = [dict(r) for r in conn.execute("SELECT home_team_id, away_team_id FROM matches")]
            rounds = services.generate_fixture(teams, played, True, True)
            if not rounds:
                click.echo("No hay partidos pendientes")
                return
            for m in rounds[0]["matches"]:
                conn.execute(
                    "INSERT INTO matches (home_team_id, away_team_id, home_goals, away_goals, created_by) "
                    "VALUES (?, ?, ?, ?, 'demo')",
                    (m["home_team_id"], m["away_team_id"], random.randint(0, 4), random.randint(0, 3)),
                )
            conn.commit()
            click.echo(f"Jornada {rounds[0]['round']} registrada ({len(rounds[0]['matches'])} partidos)")
        finally:
            conn.close()

    init_db(app)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    create_app().run(host=os.getenv("HOST", "127.0.0.1"), port=port, debug=os.getenv("FLASK_DEBUG") == "1")

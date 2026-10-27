import sqlite3
from flask import Flask, jsonify, render_template, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "champions-secret-key-2026"
jwt = JWTManager(app)


# --- CONFIGURACIÓN DE LA BASE DE DATOS SQLITE ---
def get_db_connection():
  conn = sqlite3.connect("champions.db")
  conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
  return conn


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()

  # Tabla de Equipos
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            pj INTEGER DEFAULT 0,
            pg INTEGER DEFAULT 0,
            pe INTEGER DEFAULT 0,
            pp INTEGER DEFAULT 0,
            gf INTEGER DEFAULT 0,
            gc INTEGER DEFAULT 0,
            dg INTEGER DEFAULT 0
        )
    """)

  # Tabla de Partidos
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            score TEXT NOT NULL
        )
    """)

  # Insertar datos por defecto si la tabla está vacía
  cursor.execute("SELECT COUNT(*) FROM teams")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO teams (name, country) VALUES (?, ?)",
        ("Real Madrid", "España"),
    )
    cursor.execute(
        "INSERT INTO teams (name, country) VALUES (?, ?)",
        ("Manchester City", "Inglaterra"),
    )
    conn.commit()

  conn.close()


# Inicializar la base de datos al arrancar
init_db()


# --- 0. INTERFAZ VISUAL ---
@app.route("/")
def index():
  return render_template("index.html")


# --- 1. AUTENTICACIÓN (JWT) ---
@app.route("/api/auth/login", methods=["POST"])
def login():
  data = request.get_json()
  if (
      not data
      or data.get("username") != "admin"
      or data.get("password") != "1234"
  ):
    return jsonify({"error": "Credenciales inválidas"}), 401

  access_token = create_access_token(identity=data.get("username"))
  return jsonify(access_token=access_token), 200


# --- 2. CRUD DE EQUIPOS ---
@app.route("/api/teams", methods=["GET"])
def get_teams():
  conn = get_db_connection()
  teams = conn.execute("SELECT * FROM teams").fetchall()
  conn.close()
  return jsonify([dict(row) for row in teams]), 200


@app.route("/api/teams/<int:team_id>", methods=["GET"])
def get_team_by_id(team_id):
  conn = get_db_connection()
  team = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
  conn.close()
  if not team:
    return jsonify({"error": "Equipo no encontrado"}), 404
  return jsonify(dict(team)), 200


@app.route("/api/teams", methods=["POST"])
@jwt_required()
def create_team():
  data = request.get_json()
  if not data or "name" not in data or "country" not in data:
    return jsonify({"error": "Faltan datos obligatorios (name, country)"}), 400

  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO teams (name, country) VALUES (?, ?)",
      (data.get("name"), data.get("country")),
  )
  conn.commit()
  new_id = cursor.lastrowid
  conn.close()

  return (
      jsonify({
          "id": new_id,
          "name": data.get("name"),
          "country": data.get("country"),
          "points": 0,
      }),
      201,
  )


@app.route("/api/teams/<int:team_id>", methods=["PUT"])
@jwt_required()
def update_team(team_id):
  data = request.get_json()
  conn = get_db_connection()
  team = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
  if not team:
    conn.close()
    return jsonify({"error": "Equipo no encontrado"}), 404

  new_name = data.get("name", team["name"])
  new_country = data.get("country", team["country"])

  conn.execute(
      "UPDATE teams SET name = ?, country = ? WHERE id = ?",
      (new_name, new_country, team_id),
  )
  conn.commit()
  conn.close()
  return (
      jsonify({
          "message": "Equipo actualizado con éxito",
          "id": team_id,
          "name": new_name,
          "country": new_country,
      }),
      200,
  )


@app.route("/api/teams/<int:team_id>", methods=["DELETE"])
@jwt_required()
def delete_team(team_id):
  conn = get_db_connection()
  team = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
  if not team:
    conn.close()
    return jsonify({"error": "Equipo no encontrado"}), 404

  conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
  conn.commit()
  conn.close()
  return jsonify({"message": f"Equipo {team_id} eliminado con éxito"}), 200


# --- 3. REGISTRO DE PARTIDOS Y CÁLCULO AUTOMÁTICO ---
@app.route("/api/matches", methods=["GET"])
def get_matches():
  conn = get_db_connection()
  matches = conn.execute("SELECT * FROM matches ORDER BY id DESC").fetchall()
  conn.close()
  return jsonify([dict(row) for row in matches]), 200



@app.route("/api/matches", methods=["POST"])
@jwt_required()
def register_match():
  data = request.get_json()
  local_id = data.get("home_team_id")
  away_id = data.get("away_team_id")
  home_goals = data.get("home_goals")
  away_goals = data.get("away_goals")

  if None in (local_id, away_id, home_goals, away_goals):
    return (
        jsonify({
            "error": (
                "Faltan campos (home_team_id, away_team_id, home_goals,"
                " away_goals)"
            )
        }),
        400,
    )

  conn = get_db_connection()
  home_team = conn.execute(
      "SELECT * FROM teams WHERE id = ?", (local_id,)
  ).fetchone()
  away_team = conn.execute(
      "SELECT * FROM teams WHERE id = ?", (away_id,)
  ).fetchone()

  if not home_team or not away_team:
    conn.close()
    return jsonify({"error": "Uno o ambos equipos no existen"}), 404

  # Guardar partido
  match_score = f"{home_goals} - {away_goals}"
  conn.execute(
      "INSERT INTO matches (home_team, away_team, score) VALUES (?, ?, ?)",
      (home_team["name"], away_team["name"], match_score),
  )

  # Calcular estadísticas Local
  h_pj = home_team["pj"] + 1
  h_gf = home_team["gf"] + home_goals
  h_gc = home_team["gc"] + away_goals
  h_points = home_team["points"]
  h_pg, h_pe, h_pp = home_team["pg"], home_team["pe"], home_team["pp"]

  # Calcular estadísticas Visitante
  a_pj = away_team["pj"] + 1
  a_gf = away_team["gf"] + away_goals
  a_gc = away_team["gc"] + home_goals
  a_points = away_team["points"]
  a_pg, a_pe, a_pp = away_team["pg"], away_team["pe"], away_team["pp"]

  if home_goals > away_goals:
    h_points += 3
    h_pg += 1
    a_pp += 1
  elif away_goals > home_goals:
    a_points += 3
    a_pg += 1
    h_pp += 1
  else:
    h_points += 1
    a_points += 1
    h_pe += 1
    a_pe += 1

  h_dg = h_gf - h_gc
  a_dg = a_gf - a_gc

  # Actualizar en BD (Local)
  conn.execute(
      (
          "UPDATE teams SET points = ?, pj = ?, pg = ?, pe = ?, pp = ?, gf ="
          " ?, gc = ?, dg = ? WHERE id = ?"
      ),
      (
          h_points,
          h_pj,
          h_pg,
          h_pe,
          h_pp,
          h_gf,
          h_gc,
          h_dg,
          local_id,
      ),
  )

  # Actualizar en BD (Visitante)
  conn.execute(
      (
          "UPDATE teams SET points = ?, pj = ?, pg = ?, pe = ?, pp = ?, gf ="
          " ?, gc = ?, dg = ? WHERE id = ?"
      ),
      (
          a_points,
          a_pj,
          a_pg,
          a_pe,
          a_pp,
          a_gf,
          a_gc,
          a_dg,
          away_id,
      ),
  )

  conn.commit()
  conn.close()

  return (
      jsonify({
          "message": "Partido registrado y base de datos actualizada",
          "match": {
              "home": home_team["name"],
              "away": away_team["name"],
              "score": match_score,
          },
      }),
      201,
  )


# --- 4. FUNCIONALIDAD ESPECIAL (TABLA DE POSICIONES) ---
@app.route("/api/standings", methods=["GET"])
def get_standings():
  conn = get_db_connection()
  teams = conn.execute(
      "SELECT * FROM teams ORDER BY points DESC, dg DESC, gf DESC"
  ).fetchall()
  matches_count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
  conn.close()

  return (
      jsonify({
          "status": "success",
          "total_matches_played": matches_count,
          "standings": [dict(row) for row in teams],
      }),
      200,
  )


if __name__ == "__main__":
  app.run(debug=True)
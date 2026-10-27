from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "champions-secret-key-2026"
jwt = JWTManager(app)

# Base de datos simulada en memoria
teams = [
    {"id": 1, "name": "Real Madrid", "country": "España", "points": 0, "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "dg": 0},
    {"id": 2, "name": "Manchester City", "country": "Inglaterra", "points": 0, "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "dg": 0}
]

matches = []

# --- 1. AUTENTICACIÓN (JWT) ---
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or data.get('username') != 'admin' or data.get('password') != '1234':
        return jsonify({"error": "Credenciales inválidas"}), 401
    
    access_token = create_access_token(identity=data.get('username'))
    return jsonify(access_token=access_token), 200

# --- 2. CRUD DE EQUIPOS ---
@app.route('/api/teams', methods=['GET'])
def get_teams():
    return jsonify(teams), 200

@app.route('/api/teams/<int:team_id>', methods=['GET'])
def get_team_by_id(team_id):
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify(team), 200

@app.route('/api/teams', methods=['POST'])
@jwt_required()
def create_team():
    data = request.get_json()
    if not data or 'name' not in data or 'country' not in data:
        return jsonify({"error": "Faltan datos obligatorios (name, country)"}), 400
    
    new_team = {
        "id": len(teams) + 1,
        "name": data.get('name'),
        "country": data.get('country'),
        "points": 0, "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "dg": 0
    }
    teams.append(new_team)
    return jsonify(new_team), 201

@app.route('/api/teams/<int:team_id>', methods=['PUT'])
@jwt_required()
def update_team(team_id):
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        return jsonify({"error": "Equipo no encontrado"}), 404
    
    data = request.get_json()
    team['name'] = data.get('name', team['name'])
    team['country'] = data.get('country', team['country'])
    return jsonify(team), 200

@app.route('/api/teams/<int:team_id>', methods=['DELETE'])
@jwt_required()
def delete_team(team_id):
    global teams
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        return jsonify({"error": "Equipo no encontrado"}), 404
    
    teams = [t for t in teams if t["id"] != team_id]
    return jsonify({"message": f"Equipo {team_id} eliminado con éxito"}), 200

# --- 3. REGISTRO DE PARTIDOS (ACTUALIZA TABLA AUTOMÁTICAMENTE) ---
@app.route('/api/matches', methods=['POST'])
@jwt_required()
def register_match():
    data = request.get_json()
    local_id = data.get('home_team_id')
    away_id = data.get('away_team_id')
    home_goals = data.get('home_goals')
    away_goals = data.get('away_goals')

    if None in (local_id, away_id, home_goals, away_goals):
        return jsonify({"error": "Faltan campos obligatorios (home_team_id, away_team_id, home_goals, away_goals)"}), 400

    home_team = next((t for t in teams if t["id"] == local_id), None)
    away_team = next((t for t in teams if t["id"] == away_id), None)

    if not home_team or not away_team:
        return jsonify({"error": "Uno o ambos equipos no existen"}), 404

    # Registrar el partido
    new_match = {
        "id": len(matches) + 1,
        "home_team": home_team["name"],
        "away_team": away_team["name"],
        "score": f"{home_goals} - {away_goals}"
    }
    matches.append(new_match)

    # Actualizar estadísticas del equipo Local
    home_team["pj"] += 1
    home_team["gf"] += home_goals
    home_team["gc"] += away_goals
    
    # Actualizar estadísticas del equipo Visitante
    away_team["pj"] += 1
    away_team["gf"] += away_goals
    away_team["gc"] += home_goals

    # Lógica de Puntos
    if home_goals > away_goals:
        home_team["points"] += 3
        home_team["pg"] += 1
        away_team["pp"] += 1
    elif away_goals > home_goals:
        away_team["points"] += 3
        away_team["pg"] += 1
        home_team["pp"] += 1
    else:
        home_team["points"] += 1
        away_team["points"] += 1
        home_team["pe"] += 1
        away_team["pe"] += 1

    # Diferencia de goles
    home_team["dg"] = home_team["gf"] - home_team["gc"]
    away_team["dg"] = away_team["gf"] - away_team["gc"]

    return jsonify({"message": "Partido registrado y tabla actualizada", "match": new_match}), 201

# --- 4. FUNCIONALIDAD ESPECIAL (TABLA DE POSICIONES ORDENADA) ---
@app.route('/api/standings', methods=['GET'])
def get_standings():
    # Ordenar por Puntos desc, Diferencia de goles desc, Goles a favor desc
    sorted_teams = sorted(
        teams, 
        key=lambda x: (x['points'], x['dg'], x['gf']), 
        reverse=True
    )
    return jsonify({
        "status": "success",
        "total_matches_played": len(matches),
        "standings": sorted_teams
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
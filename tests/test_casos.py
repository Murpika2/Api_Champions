"""Casos de prueba P01–P16 del proyecto integrador.

Ejecutar:  python -m pytest -v
Cada prueba lleva el código del caso para relacionarla con docs/PRUEBAS.md.
"""
import sqlite3
import threading
import time
from datetime import timedelta

from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server

import services
from conftest import ADMIN, VIEWER, login


def _count(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------- P01
def test_p01_login_correcto_y_ruta_protegida(client):
    res = client.post("/api/auth/login", json=ADMIN)
    assert res.status_code == 200
    data = res.json["data"]
    assert data["token_type"] == "Bearer" and data["expires_in"] > 0
    assert data["user"]["role"] == "admin"
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    # La ruta protegida acepta la credencial
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json["data"]["username"] == "admin"
    created = client.post("/api/teams", json={"name": "Benfica", "country": "Portugal"}, headers=headers)
    assert created.status_code == 201


# ---------------------------------------------------------------- P02
def test_p02_login_incorrecto(client):
    for creds in (
        {"username": "admin", "password": "mala"},
        {"username": "noexiste", "password": "x"},
    ):
        res = client.post("/api/auth/login", json=creds)
        assert res.status_code == 401
        assert res.json["status"] == "error"
        assert "access_token" not in str(res.json)
    # Cuerpo inválido
    assert client.post("/api/auth/login", json={"username": "admin"}).status_code == 400
    assert client.post("/api/auth/login", data="texto").status_code == 400


# ---------------------------------------------------------------- P03
def test_p03_crear_registro(client, admin_headers, db_path):
    res = client.post("/api/teams", json={"name": "  SL   Benfica ", "country": "Portugal"}, headers=admin_headers)
    assert res.status_code == 201
    team = res.json["data"]
    assert team["name"] == "SL Benfica"  # espacios normalizados
    # ID recuperable por la API
    got = client.get(f"/api/teams/{team['id']}")
    assert got.status_code == 200 and got.json["data"]["country"] == "Portugal"
    # Y presente en la base de datos
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM teams WHERE id = ?", (team["id"],)).fetchone()
    conn.close()
    assert row[0] == "SL Benfica"


# ---------------------------------------------------------------- P04
def test_p04_listar_y_filtrar(client):
    todos = client.get("/api/teams").json
    assert todos["count"] == 8
    espana = client.get("/api/teams?country=españa").json
    assert {t["name"] for t in espana["data"]} == {"Real Madrid", "FC Barcelona"}
    madrid = client.get("/api/teams?name=MADRID").json
    assert [t["name"] for t in madrid["data"]] == ["Real Madrid"]
    combinado = client.get("/api/teams?name=bar&country=alemania").json
    assert combinado["count"] == 0
    # Lista vacía: 200 con mensaje, no error
    vacio = client.get("/api/teams?name=zzzz")
    assert vacio.status_code == 200
    assert vacio.json["data"] == [] and vacio.json["message"]
    # Los comodines de SQL no se interpretan
    assert client.get("/api/teams?name=%25").json["count"] == 0


# ---------------------------------------------------------------- P05
def test_p05_actualizar(client, admin_headers):
    res = client.put("/api/teams/1", json={"name": "Real Madrid CF"}, headers=admin_headers)
    assert res.status_code == 200
    leido = client.get("/api/teams/1").json["data"]
    assert leido["name"] == "Real Madrid CF" and leido["country"] == "España"
    # No se permite un nombre repetido
    dup = client.put("/api/teams/1", json={"name": "liverpool"}, headers=admin_headers)
    assert dup.status_code == 409


# ---------------------------------------------------------------- P06
def test_p06_desactivar_y_comportamiento_posterior(client, admin_headers):
    client.post("/api/matches", json={"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 0}, headers=admin_headers)
    res = client.delete("/api/teams/1", headers=admin_headers)
    assert res.status_code == 200 and res.json["data"]["active"] is False
    # Ya no aparece en el listado ni en la tabla
    assert 1 not in [t["id"] for t in client.get("/api/teams").json["data"]]
    assert 1 not in [t["id"] for t in client.get("/api/standings").json["data"]]
    # Sí aparece pidiendo los desactivados y su ficha sigue consultable
    assert 1 in [t["id"] for t in client.get("/api/teams?include_inactive=true").json["data"]]
    assert client.get("/api/teams/1").json["data"]["active"] is False
    # El historial se conserva y el rival mantiene la derrota
    assert client.get("/api/matches").json["count"] == 1
    # No puede jugar partidos nuevos
    nuevo = client.post("/api/matches", json={"home_team_id": 3, "away_team_id": 1, "home_goals": 0, "away_goals": 0}, headers=admin_headers)
    assert nuevo.status_code == 409
    # Desactivar dos veces -> 409; reactivar -> vuelve a la tabla
    assert client.delete("/api/teams/1", headers=admin_headers).status_code == 409
    assert client.patch("/api/teams/1/activate", headers=admin_headers).status_code == 200
    assert 1 in [t["id"] for t in client.get("/api/standings").json["data"]]


# ---------------------------------------------------------------- P07
def test_p07_campos_invalidos(client, admin_headers, db_path):
    antes = _count(db_path, "teams")
    casos = [
        ({"name": "", "country": "España"}, "name"),
        ({"name": "   ", "country": "España"}, "name"),
        ({"name": 123, "country": "España"}, "name"),
        ({"name": "A", "country": "España"}, "name"),
        ({"name": "X" * 61, "country": "España"}, "name"),
        ({"name": "Club Nuevo", "country": "Esp4ña"}, "country"),
        ({"name": "Club Nuevo"}, "country"),
    ]
    for body, campo in casos:
        res = client.post("/api/teams", json=body, headers=admin_headers)
        assert res.status_code == 400, body
        assert campo in res.json["details"], body
    assert _count(db_path, "teams") == antes

    # Partido: tipos, rangos y regla "no contra sí mismo"
    res = client.post(
        "/api/matches",
        json={"home_team_id": 1, "away_team_id": 1, "home_goals": -1, "away_goals": "2"},
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert set(res.json["details"]) == {"away_team_id", "home_goals", "away_goals"}
    res = client.post("/api/matches", json={"home_team_id": 1, "away_team_id": 2, "home_goals": 100, "away_goals": True}, headers=admin_headers)
    assert res.status_code == 400
    assert _count(db_path, "matches") == 0


# ---------------------------------------------------------------- P08
def test_p08_id_inexistente(client, admin_headers):
    assert client.get("/api/teams/999").status_code == 404
    assert client.put("/api/teams/999", json={"name": "Nuevo"}, headers=admin_headers).status_code == 404
    assert client.delete("/api/teams/999", headers=admin_headers).status_code == 404
    assert client.get("/api/teams/0").status_code == 404
    assert client.get("/api/teams/abc").status_code == 404
    res = client.post("/api/matches", json={"home_team_id": 1, "away_team_id": 999, "home_goals": 1, "away_goals": 0}, headers=admin_headers)
    assert res.status_code == 404
    body = client.get("/api/teams/999").json
    assert body["status"] == "error" and "data" not in body


# ---------------------------------------------------------------- P09
def test_p09_escritura_sin_token(client, db_path):
    antes = (_count(db_path, "teams"), _count(db_path, "matches"), _count(db_path, "players"))
    peticiones = [
        client.post("/api/teams", json={"name": "Ajax", "country": "Países Bajos"}),
        client.put("/api/teams/1", json={"name": "Otro"}),
        client.delete("/api/teams/1"),
        client.post("/api/matches", json={"home_team_id": 1, "away_team_id": 2, "home_goals": 1, "away_goals": 0}),
        client.post("/api/players", json={"name": "Nadie", "team_id": 1}),
    ]
    for res in peticiones:
        assert res.status_code == 401
        assert res.json["code"] == "missing_token"
    assert (_count(db_path, "teams"), _count(db_path, "matches"), _count(db_path, "players")) == antes
    assert client.get("/api/teams/1").json["data"]["name"] == "Real Madrid"


# ---------------------------------------------------------------- P10
def test_p10_token_alterado_o_vencido(app, client, admin_headers):
    token = admin_headers["Authorization"].split()[1]
    header, payload, firma = token.split(".")
    alterados = [
        token[:-3] + ("abc" if token[-3:] != "abc" else "xyz"),  # firma cambiada
        f"{header}.{payload[:-2]}AA.{firma}",  # contenido cambiado
        "texto-cualquiera",  # no es un JWT
    ]
    for t in alterados:
        res = client.post("/api/teams", json={"name": "Ajax", "country": "Holanda"}, headers={"Authorization": f"Bearer {t}"})
        assert res.status_code == 401
        assert res.json["code"] == "invalid_token"

    # Token de prueba con expiración corta (1 segundo)
    with app.app_context():
        corto = create_access_token(identity="1", expires_delta=timedelta(seconds=1))
    ok = client.get("/api/auth/me", headers={"Authorization": f"Bearer {corto}"})
    assert ok.status_code == 200
    time.sleep(1.5)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {corto}"})
    assert res.status_code == 401 and res.json["code"] == "token_expired"

    # Token firmado con otra clave
    from flask_jwt_extended import JWTManager  # noqa: F401
    import jwt as pyjwt

    falso = pyjwt.encode({"sub": "1", "type": "access", "exp": int(time.time()) + 600}, "otra-clave-distinta-de-la-real-1234567890", algorithm="HS256")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {falso}"})
    assert res.status_code == 401


# ---------------------------------------------------------------- P11
def test_p11_persistencia_tras_reinicio(make_app):
    app1 = make_app()
    c1 = app1.test_client()
    h = login(c1, ADMIN)
    res = c1.post("/api/teams", json={"name": "Club Persistente", "country": "Colombia"}, headers=h)
    team_id = res.json["data"]["id"]
    c1.post("/api/matches", json={"home_team_id": team_id, "away_team_id": 1, "home_goals": 1, "away_goals": 0}, headers=h)

    # "Reinicio": se crea una aplicación nueva sobre el mismo archivo de base
    app2 = make_app()
    c2 = app2.test_client()
    team = c2.get(f"/api/teams/{team_id}").json["data"]
    assert team["name"] == "Club Persistente" and team["points"] == 3
    assert c2.get("/api/matches").json["count"] == 1
    # Los datos iniciales no se duplican y el login sigue funcionando
    assert c2.get("/api/teams").json["count"] == 9
    login(c2, ADMIN)


# ---------------------------------------------------------------- P12
def test_p12_interfaz_consume_api_real(client):
    """La interfaz se sirve desde la misma app y apunta a la API configurada.

    El flujo completo en navegador (login, CRUD y función especial) se
    ejecuta con tests/e2e_interfaz.py (Playwright) y se documenta con capturas.
    """
    res = client.get("/")
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert 'window.APP_CONFIG = { apiBase: "/api" }' in html
    for elemento in ("loginForm", "searchForm", "teamForm", "confirmModal", "matchForm", "calcForm", "playerForm", "fixtureForm", "koForm"):
        assert f'id="{elemento}"' in html
    # El frontend no contiene secretos
    assert "JWT_SECRET" not in html and "clave-de-pruebas" not in html
    js = client.get("/static/js/app.js").get_data(as_text=True)
    assert "clave-de-pruebas" not in js and "Admin-Prueba" not in js


# ---------------------------------------------------------------- P13
def test_p13_funcion_especial_valida(client, admin_headers):
    h = admin_headers

    def partido(a, b, ga, gb):
        r = client.post("/api/matches", json={"home_team_id": a, "away_team_id": b, "home_goals": ga, "away_goals": gb}, headers=h)
        assert r.status_code == 201, r.json
        return r.json["data"]

    # Tabla automática: 3 por victoria, 1 por empate, orden por puntos y DG
    efecto = partido(1, 2, 3, 0)["effects"]
    assert efecto[0]["points"] == 3 and efecto[0]["position_after"] == 1
    partido(3, 4, 1, 1)
    tabla = {t["id"]: t for t in client.get("/api/standings").json["data"]}
    assert (tabla[1]["points"], tabla[1]["dg"], tabla[1]["position"]) == (3, 3, 1)
    assert tabla[3]["points"] == tabla[4]["points"] == 1
    assert (tabla[2]["pp"], tabla[2]["gc"]) == (1, 3)

    # Regla: la misma localía no se repite; la vuelta sí se puede jugar
    assert client.post("/api/matches", json={"home_team_id": 1, "away_team_id": 2, "home_goals": 0, "away_goals": 0}, headers=h).status_code == 409
    partido(2, 1, 0, 1)

    # Calculadora sobre un caso conocido (función pura)
    equipos = [{"id": i, "name": n} for i, n in enumerate("ABCD", start=1)]
    jugados = []
    for local, visita in [(1, 2), (2, 1), (1, 3), (3, 1), (1, 4), (4, 1)]:  # A gana todo
        jugados.append({"home_team_id": local, "away_team_id": visita, "home_goals": 2 if local == 1 else 0, "away_goals": 0 if local == 1 else 2})
    a = services.qualification(1, equipos, jugados, spots=1)
    assert a["status"] == "clasificado" and a["current_points"] == 18 and a["matches_remaining"] == 0
    b = services.qualification(2, equipos, jugados, spots=1)
    assert b["status"] == "eliminado" and b["max_possible_points"] == 12

    # Calendario: 8 equipos -> 7 jornadas de 4 partidos por vuelta, sin repetir parejas
    cal = client.get("/api/schedule?double_round=true").json
    assert cal["total_rounds"] == 14 and cal["total_matches"] == 56
    parejas = [(m["home_team_id"], m["away_team_id"]) for r in cal["data"] for m in r["matches"]]
    assert len(set(parejas)) == 56
    for r in cal["data"]:
        ids = [x for m in r["matches"] for x in (m["home_team_id"], m["away_team_id"])]
        assert len(ids) == len(set(ids))  # nadie juega dos veces en la misma jornada
    pendientes = client.get("/api/schedule?only_pending=true").json
    assert pendientes["total_matches"] == 53

    # Eliminatoria: misma semilla -> mismo resultado; el global es la suma de ida y vuelta
    r1 = client.post("/api/knockout/simulate", json={"team1_id": 1, "team2_id": 2, "seed": 42}, headers=h).json["data"]
    r2 = client.post("/api/knockout/simulate", json={"team1_id": 1, "team2_id": 2, "seed": 42}, headers=h).json["data"]
    assert r1 == r2
    assert r1["aggregate"]["team1"] == r1["leg_1"]["home_goals"] + r1["leg_2"]["away_goals"]
    assert r1["aggregate"]["team2"] == r1["leg_1"]["away_goals"] + r1["leg_2"]["home_goals"]
    assert r1["winner"]["id"] in (1, 2)

    # Bota de Oro: agregar jugador y sumar goles cambia el ranking
    nuevo = client.post("/api/players", json={"name": "Vinícius Jr", "team_id": 1, "goals": 6}, headers=h).json["data"]
    client.patch(f"/api/players/{nuevo['id']}/goals", json={"goals": 2}, headers=h)
    top = client.get("/api/top-scorers").json["data"]
    assert top[0]["name"] == "Vinícius Jr" and top[0]["goals"] == 8


# ---------------------------------------------------------------- P14
def test_p14_funcion_especial_invalida_sin_cambios(client, admin_headers, db_path):
    h = admin_headers
    antes = (_count(db_path, "matches"), _count(db_path, "players"))
    assert client.post("/api/knockout/simulate", json={"team1_id": 1, "team2_id": 1}, headers=h).status_code == 400
    assert client.post("/api/knockout/simulate", json={"team1_id": 1, "team2_id": 999}, headers=h).status_code == 404
    assert client.post("/api/knockout/simulate", json={"team1_id": "1", "team2_id": 2}, headers=h).status_code == 400
    assert client.get("/api/teams/1/qualification?spots=8").status_code == 400  # cupos >= equipos
    assert client.get("/api/teams/1/qualification?spots=abc").status_code == 400
    assert client.get("/api/schedule?double_round=quizas").status_code == 400
    assert client.post("/api/players", json={"name": "Jugador", "team_id": 1, "goals": -3}, headers=h).status_code == 400
    assert client.post("/api/players", json={"name": "Kylian Mbappé", "team_id": 1}, headers=h).status_code == 409
    assert client.patch("/api/players/1/goals", json={"goals": 0}, headers=h).status_code == 400
    assert client.patch("/api/players/1/goals", json={"goals": -10}, headers=h).status_code == 409  # quedaría negativo
    # Resultado límite: con un solo equipo activo no hay calendario
    for tid in range(2, 9):
        client.delete(f"/api/teams/{tid}", headers=h)
    assert client.get("/api/schedule").status_code == 409
    assert (_count(db_path, "matches"), _count(db_path, "players")) == antes
    assert client.get("/api/top-scorers").json["data"][0]["goals"] == 5  # Mbappé sin cambios


# ---------------------------------------------------------------- P15
def test_p15_segundo_consumidor(app):
    """Ejecuta el cliente de consola contra un servidor real en un puerto local."""
    from consumidor.cliente import main

    server = make_server("127.0.0.1", 0, app)
    port = server.server_port
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    try:
        salida = []
        r = main(["--url", f"http://127.0.0.1:{port}", "--user", "admin", "--password", ADMIN["password"]], out=salida.append)
        texto = "\n".join(salida)
        assert r["ok"] == ["tabla", "calculadora"]
        assert "Tabla de posiciones" in texto and "Calculadora" in texto
        assert len(r["errores"]) == 1 and "HTTP 400" in r["errores"][0]
        assert "ERROR CONTROLADO" in texto

        # Error de credenciales: el cliente lo informa sin afirmar éxito
        salida = []
        r = main(["--url", f"http://127.0.0.1:{port}", "--password", "mala"], out=salida.append)
        assert r["ok"] == ["tabla"] and "HTTP 401" in r["errores"][0]
    finally:
        server.shutdown()


# ---------------------------------------------------------------- P16
def test_p16_permisos_por_rol(client, viewer_headers, db_path):
    antes = _count(db_path, "teams")
    res = client.post("/api/teams", json={"name": "Ajax", "country": "Holanda"}, headers=viewer_headers)
    assert res.status_code == 403
    assert client.delete("/api/teams/1", headers=viewer_headers).status_code == 403
    assert client.post("/api/matches", json={"home_team_id": 1, "away_team_id": 2, "home_goals": 1, "away_goals": 0}, headers=viewer_headers).status_code == 403
    assert _count(db_path, "teams") == antes
    assert client.get("/api/teams/1").json["data"]["active"] is True
    # El rol lo decide el servidor: un token sin claim de rol no da permisos de admin
    assert client.get("/api/auth/me", headers=viewer_headers).json["data"]["role"] == "viewer"
    # El usuario de solo lectura sí puede consultar y simular
    assert client.get("/api/standings", headers=viewer_headers).status_code == 200
    assert client.post("/api/knockout/simulate", json={"team1_id": 1, "team2_id": 2, "seed": 1}, headers=viewer_headers).status_code == 200


# ---------------------------------------------------------------- Extra
def test_extra_respuestas_json_y_cors(make_app, db_path):
    app = make_app(CORS_ORIGINS=["https://front.ejemplo.com"])
    c = app.test_client()
    assert c.get("/api/no-existe").json == {"status": "error", "error": "Recurso no encontrado"}
    assert c.delete("/api/standings").status_code == 405
    permitido = c.get("/api/teams", headers={"Origin": "https://front.ejemplo.com"})
    assert permitido.headers.get("Access-Control-Allow-Origin") == "https://front.ejemplo.com"
    ajeno = c.get("/api/teams", headers={"Origin": "https://malicioso.com"})
    assert "Access-Control-Allow-Origin" not in ajeno.headers


def test_extra_contrasenas_con_hash(app, db_path):
    conn = sqlite3.connect(db_path)
    hashes = [r[0] for r in conn.execute("SELECT password_hash FROM users")]
    conn.close()
    assert all(h.startswith(("scrypt:", "pbkdf2:")) for h in hashes)
    assert ADMIN["password"] not in "".join(hashes) and VIEWER["password"] not in "".join(hashes)


def test_extra_falta_secreto(monkeypatch, tmp_path):
    import pytest
    from app import create_app

    with pytest.raises(RuntimeError):
        create_app({"JWT_SECRET_KEY": "", "DATABASE_PATH": str(tmp_path / "x.db")})

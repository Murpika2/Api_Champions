"""Segundo consumidor de la API (prueba P15).

Cliente de consola independiente de la interfaz web. Hace dos operaciones
útiles y demuestra el manejo de un error:

  1. Consulta la tabla de posiciones y la imprime.
  2. Inicia sesión y consulta la calculadora de clasificación del líder.
  3. Provoca un error a propósito (registrar un partido de un equipo contra
     sí mismo) y muestra el mensaje de la API sin afirmar que funcionó.

Uso:
    pip install requests
    python consumidor/cliente.py --url https://tu-api.com --user admin --password ****

También lee API_URL, API_USER y API_PASSWORD del entorno.
"""
import argparse
import os
import sys

import requests


class ClienteApi:
    def __init__(self, base_url, timeout=10):
        self.base = base_url.rstrip("/") + "/api"
        self.timeout = timeout
        self.token = None

    def _request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            res = requests.request(method, self.base + path, headers=headers, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise RuntimeError(f"No se pudo conectar con la API: {exc}") from exc
        try:
            body = res.json()
        except ValueError:
            raise RuntimeError(f"Respuesta no válida del servidor (HTTP {res.status_code})")
        if not res.ok:
            detalle = body.get("details") or {}
            extra = " | ".join(str(v) for v in detalle.values() if isinstance(v, str))
            raise RuntimeError(f"HTTP {res.status_code}: {body.get('error')}" + (f" ({extra})" if extra else ""))
        return body

    def login(self, user, password):
        body = self._request("POST", "/auth/login", json={"username": user, "password": password})
        self.token = body["data"]["access_token"]
        return body["data"]["user"]

    def tabla(self):
        return self._request("GET", "/standings")

    def calculadora(self, team_id):
        return self._request("GET", f"/teams/{team_id}/qualification")["data"]

    def registrar_partido(self, home_id, away_id, home_goals, away_goals):
        return self._request(
            "POST",
            "/matches",
            json={"home_team_id": home_id, "away_team_id": away_id, "home_goals": home_goals, "away_goals": away_goals},
        )


def main(argv=None, out=print):
    parser = argparse.ArgumentParser(description="Cliente de consola de API Champions")
    parser.add_argument("--url", default=os.getenv("API_URL", "http://127.0.0.1:5000"))
    parser.add_argument("--user", default=os.getenv("API_USER", "admin"))
    parser.add_argument("--password", default=os.getenv("API_PASSWORD"))
    args = parser.parse_args(argv)

    api = ClienteApi(args.url)
    resultado = {"ok": [], "errores": []}

    # Operación 1: tabla de posiciones (pública)
    try:
        tabla = api.tabla()
        out(f"\n== Tabla de posiciones ({tabla['total_matches_played']} partidos jugados) ==")
        out(f"{'#':>2}  {'Equipo':<24}{'PJ':>4}{'DG':>5}{'PTS':>5}")
        for t in tabla["data"]:
            out(f"{t['position']:>2}  {t['name']:<24}{t['pj']:>4}{t['dg']:>+5}{t['points']:>5}")
        resultado["ok"].append("tabla")
    except RuntimeError as exc:
        out(f"[ERROR] No se pudo obtener la tabla: {exc}")
        resultado["errores"].append(str(exc))
        return resultado

    # Operación 2: login + calculadora de clasificación del líder
    if not args.password:
        out("\n[AVISO] Sin contraseña (--password o API_PASSWORD): se omiten las operaciones con sesión.")
        return resultado
    try:
        user = api.login(args.user, args.password)
        out(f"\nSesión iniciada como {user['username']} ({user['role']})")
        lider = tabla["data"][0]
        q = api.calculadora(lider["id"])
        out(f"== Calculadora: {lider['name']} ==")
        out(f"Estado: {q['status']} | Puntos: {q['current_points']} | Restantes: {q['matches_remaining']}")
        out(q["message"])
        resultado["ok"].append("calculadora")
    except RuntimeError as exc:
        out(f"[ERROR] {exc}")
        resultado["errores"].append(str(exc))
        return resultado

    # Manejo de un error: partido inválido (mismo equipo como local y visitante)
    try:
        api.registrar_partido(lider["id"], lider["id"], 1, 0)
        out("\n[INESPERADO] La API aceptó un partido inválido")
    except RuntimeError as exc:
        out(f"\n[ERROR CONTROLADO] La API rechazó el partido inválido -> {exc}")
        out("No se registró ningún partido.")
        resultado["errores"].append(str(exc))
    return resultado


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r["ok"] else 1)

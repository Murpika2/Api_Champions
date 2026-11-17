"""P12 – Flujo completo desde la interfaz con un navegador real (Playwright).

Levanta la aplicación con una base temporal, abre Chromium y recorre:
login (con error y correcto) -> crear -> buscar -> editar -> desactivar ->
registrar partido -> funciones especiales -> token alterado -> rol sin permisos.
Guarda capturas en docs/evidencias/.

Uso:
    pip install playwright && python -m playwright install chromium
    python tests/e2e_interfaz.py
"""
import logging
import os
import sys
import tempfile
import threading

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET_KEY", "clave-solo-para-la-prueba-e2e-1234567890-abcdef")

from playwright.sync_api import expect, sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402

OUT = os.path.join(ROOT, "docs", "evidencias")
ADMIN_PW, VIEWER_PW = "Admin-E2E-123", "Invitado-E2E-123"


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    os.makedirs(OUT, exist_ok=True)
    db = os.path.join(tempfile.mkdtemp(), "e2e.db")
    app = create_app({"DATABASE_PATH": db, "ADMIN_PASSWORD": ADMIN_PW, "VIEWER_PASSWORD": VIEWER_PW, "VIEWER_USERNAME": "invitado"})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    pasos = []

    def paso(nombre):
        pasos.append(nombre)
        print(f"  ✓ {nombre}")

    expect.set_options(timeout=10_000)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))

        def foto(nombre):
            page.wait_for_timeout(400)
            page.screenshot(path=os.path.join(OUT, f"{nombre}.png"))

        page.goto(url)
        expect(page.locator("#standingsBody tr")).to_have_count(8)
        foto("01_inicio")
        paso("La tabla carga 8 equipos desde la API")

        # Acción protegida sin sesión -> login
        page.click("#addTeamBtn")
        expect(page.locator("#loginModal")).to_be_visible()
        page.fill("#loginForm [name=username]", "admin")
        page.fill("#loginForm [name=password]", "incorrecta")
        page.click("#loginForm [type=submit]")
        expect(page.locator("#loginError")).to_contain_text("incorrectos")
        foto("02_login_incorrecto")
        paso("Login incorrecto muestra el error y no abre sesión")
        page.fill("#loginForm [name=password]", ADMIN_PW)
        page.click("#loginForm [type=submit]")
        expect(page.locator("#teamModal")).to_be_visible()
        expect(page.locator("#userChip")).to_be_visible()
        paso("Login correcto y la acción pendiente continúa sola")

        # Crear con dato inválido y luego válido
        page.fill("#teamForm [name=name]", "Real Madrid")
        page.fill("#teamForm [name=country]", "España")
        page.click("#teamForm [type=submit]")
        expect(page.locator("#teamError")).to_contain_text("Ya existe")
        page.fill("#teamForm [name=name]", "Atlético de Madrid")
        page.click("#teamForm [type=submit]")
        expect(page.locator("#teamModal")).to_be_hidden()
        expect(page.locator(".team-card", has_text="Atlético de Madrid")).to_be_visible()
        paso("Crear equipo: rechaza duplicado y crea uno válido")

        # Buscar
        page.fill("#searchName", "madrid")
        page.click("#searchForm [type=submit]")
        expect(page.locator(".team-card")).to_have_count(2)
        page.locator("#equipos").scroll_into_view_if_needed()
        foto("03_busqueda")
        page.fill("#searchName", "zzzz")
        page.click("#searchForm [type=submit]")
        expect(page.locator("#teamsGrid")).to_contain_text("No se encontraron")
        page.click("#clearSearch")
        paso("Búsqueda por nombre con resultados y sin resultados")

        # Editar
        card = page.locator(".team-card", has_text="Atlético de Madrid")
        card.locator("[data-act=edit]").click()
        page.fill("#teamForm [name=name]", "Atlético Madrid")
        page.click("#teamForm [type=submit]")
        expect(page.locator(".team-card", has_text="Atlético Madrid")).to_be_visible()
        paso("Editar equipo")

        # Desactivar con confirmación
        page.locator(".team-card", has_text="Atlético Madrid").locator("[data-act=deactivate]").click()
        expect(page.locator("#confirmModal")).to_be_visible()
        foto("04_confirmar_desactivar")
        page.click("#confirmYes")
        expect(page.locator(".team-card", has_text="Atlético Madrid")).to_have_count(0)
        page.check("#searchInactive")
        expect(page.locator(".team-card.inactive", has_text="Atlético Madrid")).to_be_visible()
        page.uncheck("#searchInactive")
        paso("Desactivar con confirmación; aparece al ver desactivados")

        # Registrar partidos
        def partido(local, visita, gl, gv):
            page.select_option("#homeTeam", label=local)
            page.select_option("#awayTeam", label=visita)
            page.fill("#homeGoals", str(gl))
            page.fill("#awayGoals", str(gv))
            page.click("#matchForm [type=submit]")

        partido("Real Madrid", "Manchester City", 3, 1)
        expect(page.locator("#matchEffects")).to_be_visible()
        partido("Liverpool", "FC Barcelona", 2, 2)
        expect(page.locator("#matchList .match-item")).to_have_count(2)
        partido("Real Madrid", "Manchester City", 0, 0)
        expect(page.locator("#matchError")).to_contain_text("Ya se jugó")
        page.locator("#partidos").scroll_into_view_if_needed()
        foto("05_partidos")
        expect(page.locator("#standingsBody tr").first).to_contain_text("Real Madrid")
        page.locator("#clasificacion").scroll_into_view_if_needed()
        foto("06_tabla_actualizada")
        paso("Registrar partidos actualiza tabla y rechaza el repetido")

        # Funciones especiales
        page.locator("#especiales").scroll_into_view_if_needed()
        page.select_option("#calcTeam", label="Real Madrid")
        page.click("#calcForm [type=submit]")
        expect(page.locator("#calcResult .result-card")).to_be_visible()
        foto("07_calculadora")
        page.click("#t-scorers")
        page.fill("#playerName", "Vinícius Jr")
        page.select_option("#playerTeam", label="Real Madrid")
        page.fill("#playerGoals", "6")
        page.click("#playerForm [type=submit]")
        fila = page.locator("#scorersBody tr", has_text="Vinícius Jr")
        expect(fila).to_be_visible()
        fila.locator("[data-goal='1']").click()
        expect(page.locator("#scorersBody tr").first).to_contain_text("Vinícius Jr")
        foto("08_bota_de_oro")
        page.click("#t-fixture")
        page.check("#fxPending")
        page.click("#fixtureForm [type=submit]")
        expect(page.locator(".round").first).to_be_visible()
        foto("09_calendario")
        page.click("#t-ko")
        page.select_option("#koTeam1", label="Real Madrid")
        page.select_option("#koTeam2", label="Liverpool")
        page.fill("#koSeed", "7")
        page.click("#koForm [type=submit]")
        expect(page.locator(".ko-winner")).to_be_visible()
        foto("10_eliminatoria")
        paso("Funciones especiales: calculadora, Bota de Oro, calendario y eliminatoria")

        # Token alterado
        page.evaluate("localStorage.setItem('champions_token', localStorage.getItem('champions_token').slice(0, -4) + 'abcd')")
        page.reload()
        expect(page.locator("#loginModal")).to_be_visible()
        expect(page.locator("#userChip")).to_be_hidden()
        foto("11_token_alterado")
        paso("Token alterado: se cierra la sesión y se pide entrar de nuevo")

        # Usuario sin permisos
        page.fill("#loginForm [name=username]", "invitado")
        page.fill("#loginForm [name=password]", VIEWER_PW)
        page.click("#loginForm [type=submit]")
        page.click("#addTeamBtn")
        page.fill("#teamForm [name=name]", "Ajax")
        page.fill("#teamForm [name=country]", "Países Bajos")
        page.click("#teamForm [type=submit]")
        expect(page.locator("#teamError")).to_contain_text("permisos")
        foto("12_rol_sin_permisos")
        paso("Usuario de solo lectura recibe el rechazo 403 de la API")

        # Celular
        movil = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        movil.goto(url)
        expect(movil.locator("#standingsBody tr").first).to_be_visible()
        movil.wait_for_timeout(500)
        movil.screenshot(path=os.path.join(OUT, "13_celular.png"))
        ancho = movil.evaluate("document.documentElement.scrollWidth")
        assert ancho <= 390, f"La página se desborda en celular ({ancho}px)"
        paso("Vista de celular sin desbordamiento horizontal")

        browser.close()
        server.shutdown()
        assert not errores, errores
    print(f"\nP12 OK: {len(pasos)} pasos. Capturas en {OUT}")


if __name__ == "__main__":
    main()

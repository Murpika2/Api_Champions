# Interfaz visual Champions League — cambios de Sebastián

Branch: `sebastian`

## Qué agregué

Una interfaz web completa, con la estética de la UEFA Champions League (azul marino profundo,
cian, plateado, balón estrellado y fondo de estrellas), servida por el mismo Flask en `http://localhost:5000/`.

| Archivo | Descripción |
|---|---|
| `templates/index.html` | Página única con cabecera, portada, clasificación, equipos, partidos y modales. |
| `static/css/styles.css` | Tema visual: colores Champions, animaciones, escudos generados, diseño responsive (móvil). |
| `static/js/app.js` | Lógica del frontend; consume todos los endpoints de la API. |
| `static/img/logo.svg` | Logo propio: balón estrellado inspirado en la Champions (usado como logo y favicon). |
| `requirements.txt` | Dependencias para instalar el proyecto fácilmente. |

## Cambios en `app.py`

- **`GET /`** → sirve la interfaz (`render_template("index.html")`).
- **`GET /api/matches`** (nuevo) → devuelve el historial de partidos (más recientes primero),
  para mostrar los últimos resultados. Antes los partidos se guardaban pero no había forma de consultarlos.

El resto de la API no se modificó.

## Funcionalidades de la interfaz

| Funcionalidad | Endpoint | Dónde |
|---|---|---|
| Iniciar / cerrar sesión (JWT, se recuerda al recargar) | `POST /api/auth/login` | Botón "Iniciar sesión" |
| Tabla de posiciones con zonas (octavos, play-off, eliminado) | `GET /api/standings` | Sección Clasificación |
| Estadísticas: equipos, partidos, goles, líder | `GET /api/standings`, `GET /api/teams` | Portada |
| Listar equipos en tarjetas con escudo y bandera | `GET /api/teams` | Sección Equipos |
| Buscar equipo por ID / ver ficha completa | `GET /api/teams/<id>` | Buscador y botón "Ver" |
| Crear equipo | `POST /api/teams` | "+ Nuevo equipo" |
| Editar equipo | `PUT /api/teams/<id>` | Botón "Editar" |
| Eliminar equipo (con confirmación) | `DELETE /api/teams/<id>` | Botón "Eliminar" |
| Registrar partido en un marcador visual | `POST /api/matches` | Sección Partidos |
| Historial de resultados | `GET /api/matches` | Sección Partidos |

Detalles extra:
- Si intentas una acción protegida sin sesión, se abre el login y, al entrar, la acción continúa sola.
- Si el token caduca, se cierra la sesión y se avisa.
- Escudos con los colores reales de los clubes conocidos (Real Madrid, City, Barça, Bayern, Liverpool, PSG…)
  y colores generados para el resto. Banderas por país.
- Notificaciones (toasts) de éxito y error, cierre de modales con `Esc`.

## Segunda entrega: interfaces para las nuevas funcionalidades de la API

Murpika agregó en `main` la gestión de jugadores y 5 funcionalidades especiales. Integré esos cambios en
la branch `sebastian` (merge de `main`) y creé una pantalla para cada una:

| Funcionalidad de la API | Endpoint | Interfaz |
|---|---|---|
| Registrar jugador | `POST /api/players` | Botón dorado "+ Nuevo jugador" (modal con nombre, equipo y goles) |
| Bota de Oro (goleadores) | `GET /api/top-scorers` | Sección **Bota de Oro**: podio animado oro/plata/bronce + ranking completo |
| Sumar goles a un jugador | `POST /api/top-scorers` | Botón "+1 ⚽" en cada goleador |
| Generador de calendario | `POST /api/schedule/generate` | Sección **Calendario**: tarjetas de cada cruce; "Registrar resultado →" lleva el cruce al marcador de Partidos |
| Simulador de eliminatoria ida y vuelta | `POST /api/knockout/simulate` | Sección **Simulador**: ida, vuelta, global y clasificado (con aviso si se decidió en penaltis) |
| Calculadora de clasificación | `GET /api/teams/<id>/qualification-calculator` | Sección **Simulador** y dentro de la ficha de cada equipo: barra de progreso, puntos que faltan y estado (En carrera / Clasificado / Eliminado) |
| Jornada del partido (`round`) | `GET /api/matches` | Etiqueta sobre cada resultado del historial |

Archivos nuevos: `static/css/features.css` y `static/js/features.js` (se cargan después de los originales).
Cambios menores en `templates/index.html` (menú con 6 secciones, nuevas secciones y modal de jugador)
y en `static/js/app.js` (avisa a `features.js` al recargar datos, muestra la jornada y la calculadora en la ficha).

## Tercera entrega: equipos reales de la Champions 2026/27

- Nuevo script `seed_champions.py`: borra todos los equipos, partidos y jugadores y carga los
  **36 clubes reales de la fase de liga 2026/27** (todos empiezan con 0 puntos) y **3 jugadores por club**
  (108 en total, todos con 0 goles).
- Jugadores tomados de la guía oficial de UEFA
  ([Meet the 2026/27 Champions League league phase teams](https://www.uefa.com/uefachampionsleague/news/02a8-2171a88881a0-c70193b972c6-1000--meet-the-2026-27-champions-league-league-phase-teams/)):
  el jugador clave, el jugador a seguir y el gran fichaje de verano de cada club.
- `champions.db` ya viene cargada con estos datos. Para volver a dejarla así en cualquier momento:
  `python seed_champions.py`.
- Escudos: colores reales y abreviaturas (PSG, BVB, ATM, SCP…) de los 36 clubes; bandera de Azerbaiyán;
  el texto del escudo se lee bien sobre cualquier combinación de colores.

## Cómo ejecutarlo

```bash
python -m venv .venv
.venv\Scripts\activate        # en Windows
pip install -r requirements.txt
python app.py
```

Abrir `http://localhost:5000/`. Usuario `admin`, contraseña `1234`.

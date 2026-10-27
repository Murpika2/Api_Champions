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

## Cómo ejecutarlo

```bash
python -m venv .venv
.venv\Scripts\activate        # en Windows
pip install -r requirements.txt
python app.py
```

Abrir `http://localhost:5000/`. Usuario `admin`, contraseña `1234`.

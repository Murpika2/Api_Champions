# API Champions ⚽

API REST con interfaz web para **gestionar un torneo de fútbol tipo Champions League**: equipos, resultados, tabla de posiciones automática, calculadora de clasificación, Bota de Oro, calendario y simulador de eliminatorias.

Proyecto integrador · *Cloud: Desarrollo de APIs e integración de servicios en la nube* · USTA Tunja

---

## 1. Problemática

En los torneos de fútbol universitarios, de barrio o empresariales, la tabla de posiciones suele llevarse **a mano o en hojas de cálculo**. Eso provoca:

- **Errores de cálculo** de puntos, diferencia de goles o desempates.
- **Partidos duplicados** o mal registrados que nadie detecta.
- Preguntas sin respuesta clara, como *"¿cuántos puntos necesitamos para clasificar?"*.
- Información que **solo tiene el organizador** y que los equipos no pueden consultar.

**API Champions** resuelve esto con un sistema en la nube que:

1. Calcula la tabla automáticamente a partir de los resultados, sin cálculos manuales.
2. Aplica las reglas del torneo: un equipo no juega contra sí mismo y cada pareja juega una sola vez de local.
3. Responde matemáticamente si un equipo ya clasificó, quedó eliminado o cuántas victorias necesita.
4. Permite consultar todo públicamente, mientras que solo el administrador puede modificar datos.

## 2. Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Autenticación** | Login con JWT firmado y con expiración. Contraseñas guardadas con hash. Roles `admin` y `viewer` (solo lectura). |
| **Equipos (CRUD)** | Crear, listar, buscar por nombre o país, consultar, editar, **desactivar** y reactivar. |
| **Partidos** | Registrar resultados (la tabla se recalcula sola), ver el historial y anular partidos mal registrados. |
| **⭐ Función especial: motor del torneo** | Tabla automática con estado de clasificación, **calculadora de clasificación**, **calendario** todos contra todos, **simulador de eliminatorias** ida y vuelta y **Bota de Oro**. |
| **Interfaz web** | Una sola página (HTML, CSS y JS sin frameworks) que consume la API real. Funciona en computador y celular. |
| **Segundo consumidor** | Cliente de consola en Python (`consumidor/cliente.py`). |

### Reglas de negocio

- Victoria = 3 puntos, empate = 1, derrota = 0. La tabla se ordena por **puntos → diferencia de gol → goles a favor → nombre**.
- Liga todos contra todos a ida y vuelta: **cada pareja juega una vez con cada equipo como local**. Un partido repetido responde 409.
- Un equipo **no se borra físicamente**: se *desactiva*. Sus partidos son parte de la historia del torneo y de los puntos de sus rivales. Un equipo desactivado no aparece en listados ni en la tabla, no puede jugar y sus jugadores salen de la Bota de Oro. Se puede reactivar.
- Cupos de clasificación: los definidos en `QUALIFICATION_SPOTS` o, por defecto, la mitad de los equipos activos.

## 3. Arquitectura

```
Navegador (templates/index.html + static/js/app.js)       consumidor/cliente.py
                 │  fetch + JWT (Authorization: Bearer)          │ requests
                 └──────────────────────┬────────────────────────┘
                                        ▼
                       Flask  (app.py · rutas /api/*)
          validators.py ── validación de datos y errores JSON
          services.py   ── lógica del torneo (funciones puras)
          database.py   ── SQLite, consultas parametrizadas
                                        ▼
                    data/champions.db  (volumen persistente)
```

| Archivo | Responsabilidad |
|---|---|
| `app.py` | Fábrica de la app, rutas de la API, autenticación, roles, manejo de errores y comandos CLI |
| `config.py` | Lee **todas** las variables de entorno (`.env`) |
| `database.py` | Esquema SQLite, conexión por petición y datos iniciales |
| `validators.py` | Validación de campos (obligatorios, tipos, textos vacíos, rangos) |
| `services.py` | Tabla, calculadora, calendario y simulador (sin acceso a la base, fácil de probar) |
| `wsgi.py` | Punto de entrada para gunicorn o PythonAnywhere |
| `templates/`, `static/` | Interfaz web |
| `consumidor/cliente.py` | Segundo consumidor (cliente de consola) |
| `tests/` | 16 casos de prueba (pytest) y prueba de interfaz en navegador (Playwright) |
| `docs/` | Colección Postman, pruebas documentadas, guía de despliegue y evidencias |

## 4. Requisitos

- **Python 3.10 o superior** (probado con 3.11 y 3.13)
- pip
- Git (opcional)

Dependencias (`requirements.txt`): Flask 3, Flask-JWT-Extended 4, Flask-CORS, python-dotenv y gunicorn (solo Linux).

## 5. Instalación y ejecución local

```bash
git clone https://github.com/Murpika2/Api_Champions.git
cd Api_Champions

python -m venv .venv
# Windows:     .venv\Scripts\activate
# Mac/Linux:   source .venv/bin/activate

pip install -r requirements.txt

# Configuración: copiar la plantilla y editarla
copy .env.example .env        # Windows   (Mac/Linux: cp .env.example .env)
```

Edita `.env` y define como mínimo:

```ini
JWT_SECRET_KEY=<clave aleatoria>     # genera una con: python -c "import secrets; print(secrets.token_hex(32))"
ADMIN_PASSWORD=<tu contraseña de administrador>
VIEWER_PASSWORD=<contraseña del usuario de solo lectura>   # opcional
```

Inicia el servidor:

```bash
python app.py
```

Abre **http://127.0.0.1:5000**. La primera vez se crean automáticamente:

- Las tablas `users`, `teams`, `matches` y `players` en `data/champions.db`.
- El usuario `admin` (y `invitado`, si definiste `VIEWER_PASSWORD`), con la contraseña guardada con hash.
- 8 equipos y 8 goleadores de ejemplo (si `SEED_DEMO_DATA=true`).

### Carga de datos y comandos útiles

```bash
flask --app app init-db                       # crea las tablas y los datos iniciales
flask --app app demo-matches                  # registra una jornada con resultados aleatorios
flask --app app create-user profe --role viewer   # crea otro usuario (pide la contraseña)
```

Para empezar desde cero, borra `data/champions.db` y vuelve a iniciar.

### Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `JWT_SECRET_KEY` | ✅ | Clave para firmar los tokens (mínimo 32 caracteres) |
| `ADMIN_PASSWORD` | ✅ (primera vez) | Contraseña del administrador inicial |
| `ADMIN_USERNAME` | | Usuario administrador (por defecto `admin`) |
| `VIEWER_USERNAME` / `VIEWER_PASSWORD` | | Usuario de solo lectura |
| `JWT_EXPIRES_MINUTES` | | Duración del token (por defecto 60) |
| `DATABASE_PATH` | | Ruta del archivo SQLite (por defecto `data/champions.db`) |
| `SEED_DEMO_DATA` | | Cargar equipos de ejemplo si la base está vacía (`true`) |
| `QUALIFICATION_SPOTS` | | Cupos de clasificación (0 = la mitad de los equipos) |
| `FRONTEND_API_BASE` | | Dirección de la API que usa la interfaz (por defecto `/api`) |
| `CORS_ORIGINS` | | Orígenes permitidos, separados por coma (vacío = solo el mismo origen) |

> El `.env` **nunca se sube al repositorio** (está en `.gitignore`). El frontend no contiene la clave JWT ni credenciales.

## 6. Endpoints

Base: `/api`. Todas las respuestas son JSON:

- Éxito: `{"status": "success", "message": ..., "data": ...}`
- Error: `{"status": "error", "error": "mensaje", "details": {"campo": "motivo"}}`

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/auth/login` | — | Iniciar sesión → JWT |
| GET | `/auth/me` | token | Usuario actual |
| GET | `/health` | — | Estado del servicio |
| GET | `/teams?name=&country=&include_inactive=` | — | Listar y buscar equipos |
| GET | `/teams/{id}` | — | Detalle de un equipo |
| POST | `/teams` | admin | Crear equipo |
| PUT | `/teams/{id}` | admin | Editar equipo |
| DELETE | `/teams/{id}` | admin | Desactivar equipo |
| PATCH | `/teams/{id}/activate` | admin | Reactivar equipo |
| GET | `/matches?team_id=` | — | Historial de partidos |
| POST | `/matches` | admin | Registrar partido |
| DELETE | `/matches/{id}` | admin | Anular partido |
| GET | `/standings` | — | ⭐ Tabla con estado de clasificación |
| GET | `/teams/{id}/qualification?spots=` | — | ⭐ Calculadora de clasificación |
| GET | `/schedule?double_round=&only_pending=` | — | ⭐ Calendario |
| POST | `/knockout/simulate` | token | ⭐ Simulador de eliminatoria |
| GET | `/top-scorers?limit=` | — | ⭐ Bota de Oro |
| GET | `/players?team_id=` | — | Jugadores |
| POST | `/players` | admin | Agregar jugador |
| PATCH | `/players/{id}/goals` | admin | Sumar o corregir goles |
| DELETE | `/players/{id}` | admin | Eliminar jugador |

**Códigos HTTP:** 200 OK · 201 creado · 400 datos inválidos · 401 sin token, token alterado o vencido · 403 rol sin permiso · 404 no existe · 409 conflicto con una regla del negocio · 500 error interno.

📄 La documentación completa, con método, propósito, parámetros, cuerpo y ejemplos reales de éxito y error, está en **`docs/API_Champions.postman_collection.json`**. Impórtala en Postman, cambia `base_url`, `username` y `password`, y ejecuta *Iniciar sesión*: el token se guarda solo.

## 7. Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest -v                 # casos P01–P16 (+3 extra)
python tests/e2e_interfaz.py        # P12 en navegador real (requiere: pip install playwright && python -m playwright install chromium)
python consumidor/cliente.py --url http://127.0.0.1:5000 --password <tu contraseña>   # P15
```

El detalle de cada caso, con pasos, resultado esperado y resultado obtenido, está en **`docs/PRUEBAS.md`**. Las capturas están en `docs/evidencias/`.

## 8. Despliegue en la nube

Guía paso a paso en **`docs/DESPLIEGUE.md`**. Recomendado: **PythonAnywhere**, que ofrece HTTPS y disco persistente para SQLite en el plan gratuito.

## 9. Cumplimiento de requisitos

| Requisito | Cómo se cumple |
|---|---|
| RF01 CRUD | `/teams`: crear, listar, consultar, editar y desactivar/reactivar (borrado lógico justificado arriba) |
| RF02 Consulta útil | `GET /teams?name=&country=` con coincidencia parcial; la lista vacía responde 200 con mensaje |
| RF03 Autenticación | JWT HS256 firmado con expiración; rechaza tokens ausentes, alterados, vencidos o de usuarios eliminados |
| RF04 Permisos | Las escrituras exigen rol `admin`, leído de la base de datos en el servidor (403 si no lo tiene) |
| RF05 Validaciones | Obligatorios, tipos, textos vacíos, longitudes, rangos de goles, IDs y reglas del torneo |
| RF06 Respuestas | Formato JSON único para éxito y error; manejadores para 404, 405, 415 y 500 |
| RF07 Persistencia | SQLite en archivo; prueba P11 con reinicio real |
| RF08 Protección | Hash scrypt para contraseñas, secretos en `.env` y consultas parametrizadas (`?`) |
| RF10 Función especial | Motor del torneo (5 funciones) |
| UI01–UI04 | Sesión con validación del token, CRUD y búsqueda, funciones especiales, estados de carga, éxito, error y vacío, teclado y celular |
| NU01–NU05 | Ver `docs/DESPLIEGUE.md`, `.env.example` y este README |
| Pruebas | 16 casos automatizados + prueba de interfaz + evidencias |

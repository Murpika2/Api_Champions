# Casos de prueba P01–P16

Todas las pruebas se pueden repetir:

| Herramienta | Comando | Cubre |
|---|---|---|
| pytest | `python -m pytest -v` | P01–P16 + 3 extra, con una base temporal nueva en cada prueba |
| Playwright | `python tests/e2e_interfaz.py` | P12 en un navegador real; guarda capturas en `docs/evidencias/` |
| Cliente de consola | `python consumidor/cliente.py --url <URL> --password <clave>` | P15 contra el servidor local o publicado |
| Postman | `docs/API_Champions.postman_collection.json` | Manual / Newman; ejemplos de cada caso |

**Datos de partida:** base vacía con 8 equipos de ejemplo (IDs 1–8: Real Madrid, Manchester City, FC Barcelona, Bayern Múnich, Liverpool, Paris Saint-Germain, Inter de Milán, Borussia Dortmund), 8 goleadores, el usuario `admin` (rol admin) y el usuario `invitado` (rol viewer).

**Resultado de la última ejecución:**

```
tests/test_casos.py::test_p01_login_correcto_y_ruta_protegida PASSED
tests/test_casos.py::test_p02_login_incorrecto PASSED
tests/test_casos.py::test_p03_crear_registro PASSED
tests/test_casos.py::test_p04_listar_y_filtrar PASSED
tests/test_casos.py::test_p05_actualizar PASSED
tests/test_casos.py::test_p06_desactivar_y_comportamiento_posterior PASSED
tests/test_casos.py::test_p07_campos_invalidos PASSED
tests/test_casos.py::test_p08_id_inexistente PASSED
tests/test_casos.py::test_p09_escritura_sin_token PASSED
tests/test_casos.py::test_p10_token_alterado_o_vencido PASSED
tests/test_casos.py::test_p11_persistencia_tras_reinicio PASSED
tests/test_casos.py::test_p12_interfaz_consume_api_real PASSED
tests/test_casos.py::test_p13_funcion_especial_valida PASSED
tests/test_casos.py::test_p14_funcion_especial_invalida_sin_cambios PASSED
tests/test_casos.py::test_p15_segundo_consumidor PASSED
tests/test_casos.py::test_p16_permisos_por_rol PASSED
tests/test_casos.py::test_extra_respuestas_json_y_cors PASSED
tests/test_casos.py::test_extra_contrasenas_con_hash PASSED
tests/test_casos.py::test_extra_falta_secreto PASSED
============================== 19 passed ==============================
```

Ejecutado en Python 3.11 y 3.13. La prueba de navegador terminó con `P12 OK: 12 pasos`.

---

## Resumen

| Caso | Escenario | Resultado esperado | Obtenido |
|---|---|---|---|
| P01 | Login correcto | Token válido; una ruta protegida lo acepta | ✅ |
| P02 | Login incorrecto | 401, sin token | ✅ |
| P03 | Crear registro | 201, ID consultable por API y en la base | ✅ |
| P04 | Listar y filtrar | Coincidencias correctas; lista vacía controlada | ✅ |
| P05 | Actualizar | La lectura posterior muestra el cambio | ✅ |
| P06 | Desactivar | Cambio confirmado y comportamiento posterior documentado | ✅ |
| P07 | Campos inválidos | 400 por tipo, campo vacío o rango; nada se guarda | ✅ |
| P08 | ID inexistente | 404 sin devolver otro registro | ✅ |
| P09 | Escritura sin token | 401 y la base sin cambios | ✅ |
| P10 | Token alterado o vencido | 401 (`invalid_token` / `token_expired`) | ✅ |
| P11 | Reinicio / nuevo despliegue | El registro se conserva | ✅ |
| P12 | Flujo desde la interfaz | Acceso, CRUD y función especial con la API real | ✅ |
| P13 | Función especial válida | Cálculos iguales a lo esperado | ✅ |
| P14 | Función especial inválida | Rechazo coherente, sin cambios en la base | ✅ |
| P15 | Segundo consumidor | Dos operaciones útiles y un error manejado | ✅ |
| P16 | Permisos por rol | 403 para el rol sin permiso y la base sin cambios | ✅ |

---

## Detalle de cada caso

### P01 · Login correcto
**Pasos:** `POST /api/auth/login` con `{"username": "admin", "password": "<clave>"}` → con el token, `GET /api/auth/me` y `POST /api/teams`.
**Esperado:** 200 con `access_token`, `token_type: "Bearer"`, `expires_in > 0` y rol `admin`. `/auth/me` responde 200 y el equipo se crea con 201.
**Obtenido:** igual al esperado. Evidencia: `docs/evidencias/01_inicio.png` y el ejemplo "Login correcto" en Postman.

### P02 · Login incorrecto
**Pasos:** contraseña errónea; usuario inexistente; cuerpo sin contraseña; cuerpo que no es JSON.
**Esperado:** 401 `"Usuario o contraseña incorrectos"` (el mismo mensaje en los dos casos, para no revelar qué falló), sin token; 400 cuando falta un campo o el JSON es inválido. La interfaz muestra el error y no abre sesión.
**Obtenido:** igual al esperado. Evidencia: `02_login_incorrecto.png`.

### P03 · Crear registro
**Pasos:** `POST /api/teams` `{"name": "  SL   Benfica ", "country": "Portugal"}` → `GET /api/teams/{id}` → consulta directa a SQLite.
**Esperado:** 201 con el ID nuevo y el nombre normalizado (`"SL Benfica"`). La lectura por ID y la fila en la tabla `teams` coinciden.
**Obtenido:** igual al esperado.

### P04 · Listar y filtrar
**Pasos:** `GET /api/teams`; `?country=españa`; `?name=MADRID`; `?name=bar&country=alemania`; `?name=zzzz`; `?name=%`.
**Esperado:** 8 equipos; España → Real Madrid y FC Barcelona (sin importar mayúsculas); MADRID → Real Madrid; combinación sin coincidencias → `count: 0`; `zzzz` → 200 con `data: []` y el mensaje "No se encontraron equipos…"; el comodín `%` no se interpreta como "todo".
**Obtenido:** igual al esperado. Evidencia: `03_busqueda.png`.

### P05 · Actualizar
**Pasos:** `PUT /api/teams/1` `{"name": "Real Madrid CF"}` → `GET /api/teams/1`; luego intentar renombrarlo como `"liverpool"`.
**Esperado:** 200; la lectura posterior muestra el nombre nuevo y conserva el país. El nombre repetido responde 409.
**Obtenido:** igual al esperado.

### P06 · Eliminar o desactivar
**Regla:** el equipo se **desactiva** (borrado lógico) porque sus partidos forman parte de la historia del torneo.
**Pasos:** registrar un partido 1 vs 2 → `DELETE /api/teams/1` → consultar listado, tabla, `?include_inactive=true`, la ficha y el historial → intentar un partido nuevo con el equipo 1 → desactivar otra vez → `PATCH /api/teams/1/activate`.
**Esperado / comportamiento posterior:** 200 con `active: false`. El equipo sale del listado y de la tabla, pero aparece con `include_inactive`. La ficha sigue consultable. El partido se conserva en el historial. Un partido nuevo con el equipo 1 → 409. Desactivar dos veces → 409. Al reactivarlo vuelve a la tabla.
**Obtenido:** igual al esperado. Evidencia: `04_confirmar_desactivar.png` (confirmación en la interfaz).

### P07 · Campos inválidos
**Pasos:** crear equipos con nombre vacío, solo espacios, numérico, de 1 carácter, de 61 caracteres, país con números o sin país. Registrar un partido con el mismo equipo, goles negativos, goles como texto, 100 goles o `true`.
**Esperado:** 400 `"Datos inválidos"`, con `details` indicando cada campo. La cantidad de equipos y partidos no cambia.
**Obtenido:** igual al esperado. Ejemplo de respuesta:
```json
{"status": "error", "error": "Datos inválidos",
 "details": {"home_goals": "'goles local' debe ser mayor o igual a 0",
             "away_goals": "'goles visitante' debe ser un número entero",
             "away_team_id": "Un equipo no puede jugar contra sí mismo"}}
```

### P08 · ID inexistente
**Pasos:** GET, PUT y DELETE de `/api/teams/999`; `/api/teams/0`; `/api/teams/abc`; un partido con `away_team_id: 999`.
**Esperado:** 404 con `status: "error"` y **sin** campo `data` (no se devuelve otro registro).
**Obtenido:** igual al esperado.

### P09 · Escritura sin token
**Pasos:** POST, PUT y DELETE de equipos, POST de partidos y de jugadores sin la cabecera `Authorization`.
**Esperado:** 401 con `code: "missing_token"`. Las cantidades de equipos, partidos y jugadores no cambian.
**Obtenido:** igual al esperado.

### P10 · Token alterado o vencido
**Pasos:**
1. Token con la firma modificada, con el contenido modificado y con texto que no es JWT → 401 `invalid_token`.
2. **Token de prueba con expiración de 1 segundo**: funciona inmediatamente; tras 1,5 s → 401 `token_expired`.
3. Token firmado con otra clave → 401.
4. En la interfaz: se altera el token guardado y se recarga la página → la sesión se cierra y se pide entrar de nuevo.
5. Reinicio real del servidor con otra `JWT_SECRET_KEY`: el token anterior → 401.

**Obtenido:** igual al esperado. Evidencia: `11_token_alterado.png`.

### P11 · Reinicio o nuevo despliegue
**Pasos (pytest):** crear "Club Persistente" y un partido → crear una **aplicación nueva** sobre el mismo archivo de base → consultar.
**Pasos (servidor real, gunicorn):** crear "Club Reinicio" → detener el servidor (health = sin respuesta) → iniciarlo de nuevo → `GET /api/teams?name=reinicio`.
**Esperado:** los registros y los puntos se conservan; los datos de ejemplo no se duplican; el login sigue funcionando.
**Obtenido:** igual al esperado (`tras reinicio: 1 ['Club Reinicio']`).
**En la nube:** repetir con **Reload** en PythonAnywhere (ver `docs/DESPLIEGUE.md`, paso 7).

### P12 · Flujo desde la interfaz
**Pasos (`tests/e2e_interfaz.py`, navegador Chromium):**
1. La tabla carga 8 equipos desde la API.
2. "+ Nuevo equipo" sin sesión → se abre el login; la contraseña incorrecta muestra el error.
3. Login correcto → el formulario continúa solo.
4. Nombre duplicado rechazado → se crea "Atlético de Madrid".
5. Búsqueda "madrid" (2 resultados) y "zzzz" (mensaje de vacío).
6. Edición del equipo.
7. Desactivación con confirmación; aparece al marcar "Ver desactivados".
8. Registro de partidos con el efecto en la tabla; el partido repetido se rechaza.
9. Funciones especiales: calculadora, Bota de Oro (agregar jugador y +1 gol), calendario y eliminatoria.
10. Token alterado → sesión cerrada.
11. Usuario `invitado` → 403 visible en el formulario.
12. Vista de celular (390 px) sin desbordamiento.

**Obtenido:** `P12 OK: 12 pasos`, sin errores de JavaScript. Evidencia: `docs/evidencias/01…13`.

### P13 · Función especial válida
| Función | Caso | Esperado | Obtenido |
|---|---|---|---|
| Tabla | Real Madrid 3–0 City; Barça 1–1 Bayern | RM 3 pts, DG +3, 1º; Barça y Bayern 1 pt; City PP=1, GC=3 | ✅ |
| Regla de localía | Repetir RM (local) vs City; luego City (local) vs RM | 409; la vuelta se acepta (201) | ✅ |
| Calculadora | 4 equipos, 1 cupo, A ganó sus 6 partidos | A `clasificado` (18 pts, 0 restantes); B `eliminado` (máximo 12) | ✅ |
| Calendario | 8 equipos, ida y vuelta | 14 jornadas, 56 partidos, sin parejas repetidas, nadie juega 2 veces por jornada; con 3 jugados → 53 pendientes | ✅ |
| Eliminatoria | RM vs City, `seed: 42`, dos veces | Resultado idéntico; global = ida + vuelta | ✅ |
| Bota de Oro | Agregar "Vinícius Jr" con 6 goles y sumar 2 | Queda 1º con 8 goles | ✅ |

Además, el registro de un partido devuelve el **efecto en la tabla** (posición antes y después y puntos), que la interfaz muestra en "Efecto en la tabla" (`05_partidos.png`).

### P14 · Función especial inválida
**Pasos:** eliminatoria con el mismo equipo (400), con un equipo inexistente (404) o con ID como texto (400); calculadora con `spots=8` siendo 8 equipos (400) o `spots=abc` (400); calendario con `double_round=quizas` (400); jugador con goles negativos (400) o repetido (409); sumar 0 goles (400); restar 10 goles a Mbappé que tiene 5 (409, quedaría negativo); calendario con un solo equipo activo (409).
**Esperado:** rechazo coherente; **ningún partido ni jugador cambia** (se comparan los conteos antes y después) y Mbappé sigue con 5 goles.
**Obtenido:** igual al esperado.

### P15 · Segundo consumidor
**Consumidor:** `consumidor/cliente.py`, un cliente de consola en Python con `requests`, independiente de la interfaz.
**Operaciones:** (1) imprime la tabla de posiciones; (2) inicia sesión y consulta la calculadora del líder; (3) envía a propósito un partido inválido y muestra el error sin afirmar éxito. Con una contraseña incorrecta informa el 401.
**Obtenido:**
```
== Tabla de posiciones (1 partidos jugados) ==
 #  Equipo                    PJ   DG  PTS
 1  Real Madrid                1   +2    3
 ...
Sesión iniciada como admin (admin)
== Calculadora: Real Madrid ==
Estado: en_disputa | Puntos: 3 | Restantes: 17
Asegura la clasificación si gana 16 de sus 17 partidos restantes, ...
[ERROR CONTROLADO] La API rechazó el partido inválido -> HTTP 400: Datos inválidos (Un equipo no puede jugar contra sí mismo)
No se registró ningún partido.
```

### P16 · Permisos o validación adicional
**Pasos:** con el usuario `invitado` (rol `viewer`): crear un equipo, desactivar un equipo y registrar un partido. Luego consultar la tabla y simular una eliminatoria.
**Esperado:** 403 `"No tienes permisos para esta acción (requiere rol administrador)"` en las escrituras, sin cambios en la base; las consultas y la simulación sí funcionan. El rol se lee de la base de datos en el servidor, no del cliente.
**Obtenido:** igual al esperado. Evidencia: `12_rol_sin_permisos.png`.

---

## Pruebas extra

- **Respuestas JSON y CORS:** las rutas inexistentes responden 404 en JSON y los métodos no permitidos 405. Un origen autorizado recibe `Access-Control-Allow-Origin`; uno ajeno no.
- **Contraseñas con hash:** la tabla `users` guarda hashes `scrypt:`; las contraseñas en texto plano no aparecen.
- **Secreto obligatorio:** la app no arranca sin `JWT_SECRET_KEY` (o si tiene menos de 32 caracteres).

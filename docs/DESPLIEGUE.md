# Despliegue en la nube (NU01–NU05)

La API y la interfaz se publican **juntas** en un mismo servidor. Flask entrega la página en `/` y la API en `/api`, así que comparten origen y no hace falta CORS para la interfaz.

## ¿Dónde desplegar?

El proyecto usa **SQLite**, y el requisito NU02 exige que el archivo esté en un **disco persistente**.

| Plataforma | ¿Sirve? | Motivo |
|---|---|---|
| **PythonAnywhere (gratis)** | ✅ **Recomendada** | Disco persistente de 512 MiB, HTTPS en `tuusuario.pythonanywhere.com`, soporte nativo para Flask. La app gratuita **vence al mes** si no la renuevas con un botón. |
| Railway / Render / Fly.io **con volumen** | ✅ | Requieren plan de pago o crédito. Montar el volumen y apuntar `DATABASE_PATH` a él. |
| Render **gratis** | ❌ | El disco de los servicios gratuitos es temporal: se borra al reiniciar o redesplegar, y no permite discos persistentes. |

---

## Opción recomendada: PythonAnywhere

> ✅ **Desplegado en:** https://sebastianag.pythonanywhere.com (API en `/api`, salud en `/api/health`). Vence el 17 de diciembre de 2026 si no se renueva.

### 1. Crear la cuenta

Regístrate en https://www.pythonanywhere.com con una cuenta *Beginner* (gratis). Tu dirección será `https://TUUSUARIO.pythonanywhere.com`.

### 2. Subir el código

En **Consoles → Bash**:

```bash
git clone https://github.com/Murpika2/Api_Champions.git
cd Api_Champions
git checkout entrega-final        # o la rama donde esté la entrega
```

### 3. Crear el entorno virtual e instalar dependencias

```bash
/usr/bin/python3.13 -m venv ~/.virtualenvs/champions-venv
source ~/.virtualenvs/champions-venv/bin/activate
pip install -r requirements.txt
```

### 4. Configurar las variables (`.env`)

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"     # copia el resultado
nano .env
```

Valores para producción:

```ini
JWT_SECRET_KEY=<la clave que generaste>
JWT_EXPIRES_MINUTES=60
DATABASE_PATH=/home/TUUSUARIO/Api_Champions/data/champions.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<contraseña segura>
VIEWER_USERNAME=invitado
VIEWER_PASSWORD=<otra contraseña>
SEED_DEMO_DATA=true
FRONTEND_API_BASE=/api
CORS_ORIGINS=
FLASK_DEBUG=0
```

Guarda con `Ctrl+O`, `Enter` y `Ctrl+X`. Luego crea la base:

```bash
flask --app app init-db
```

### 5. Crear la aplicación web

1. Ve a **Web → Add a new web app → Next**.
2. Elige **Manual configuration** (no "Flask") y **Python 3.13**.
3. En **Virtualenv** escribe: `/home/TUUSUARIO/.virtualenvs/champions-venv`.
   (Nota: en PythonAnywhere el entorno creado con `mkvirtualenv` y Python 3.11 falló al instalar con pip; con Python 3.13 y `python -m venv` funciona.)
4. En **Code → WSGI configuration file**, abre el archivo, **borra todo** y deja solo esto:

```python
import sys

path = "/home/TUUSUARIO/Api_Champions"
if path not in sys.path:
    sys.path.insert(0, path)

from wsgi import application  # noqa
```

5. (Opcional, más rápido) En **Static files** agrega: URL `/static/` → Directory `/home/TUUSUARIO/Api_Champions/static`.
6. En **Security**, activa **Force HTTPS**.
7. Pulsa el botón verde **Reload**.

### 6. Verificar

- `https://TUUSUARIO.pythonanywhere.com/api/health` debe responder `{"status": "success", ...}`.
- `https://TUUSUARIO.pythonanywhere.com/` debe mostrar la interfaz. Inicia sesión con `admin`.
- Desde **otro equipo o desde el celular** abre la misma dirección (requisito "accesible desde otro equipo").
- En Postman, cambia `base_url` a `https://TUUSUARIO.pythonanywhere.com` y ejecuta la colección.
- Segundo consumidor: `python consumidor/cliente.py --url https://TUUSUARIO.pythonanywhere.com --password <contraseña>`.

Si algo falla, revisa **Web → Log files → Error log**.

### 7. Prueba P11 en la nube (persistencia)

1. Crea un equipo desde la interfaz publicada.
2. En la pestaña **Web**, pulsa **Reload** (reinicia la aplicación).
3. Recarga la página: el equipo sigue ahí.
4. Para simular un nuevo despliegue: `cd ~/Api_Champions && git pull` y luego **Reload**. Los datos se conservan porque `data/` no está en Git.

### 8. Mantenimiento

- **La app gratuita vence al mes.** Entra a **Web** y pulsa **"Run until 1 month from today"** antes de la fecha de sustentación.
- Actualizar el código: `git pull` en la consola y luego **Reload**.
- Copia de seguridad: descarga `data/champions.db` desde la pestaña **Files**.

---

## Alternativa: plataforma con volumen (Railway, Render de pago, Fly.io)

1. Crea un servicio web desde el repositorio de GitHub.
2. **Comando de inicio:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
3. Crea un **volumen** montado en `/data`.
4. Variables de entorno: las mismas del `.env`, con `DATABASE_PATH=/data/champions.db`.
5. Activa el dominio público con HTTPS que ofrece la plataforma.

## Si el frontend se publica aparte

Si la interfaz se sirve desde otro dominio (por ejemplo, Netlify):

- En la API: `CORS_ORIGINS=https://tu-frontend.netlify.app`
- En el HTML: cambia `window.APP_CONFIG.apiBase` por `https://tu-api.com/api`.

La API solo responde con la cabecera `Access-Control-Allow-Origin` a los orígenes de esa lista (prueba `test_extra_respuestas_json_y_cors`).

## Checklist antes de entregar

- [ ] `JWT_SECRET_KEY` y las contraseñas reales están solo en el `.env` del servidor, no en GitHub.
- [ ] `https://.../api/health` responde.
- [ ] La interfaz abre desde otro equipo y desde el celular.
- [ ] La colección Postman funciona con `base_url` apuntando a la nube.
- [ ] Prueba P11 hecha en la nube (Reload y el dato sigue).
- [ ] La app está renovada por un mes más en PythonAnywhere.

"""Punto de entrada para servidores de producción.

- gunicorn:        gunicorn wsgi:app
- PythonAnywhere:  from wsgi import application
"""
from app import create_app

app = create_app()
application = app

"""Errores de la API y validación de datos de entrada (RF05 / RF06)."""
import re

from flask import request


class ApiError(Exception):
    """Error controlado que se devuelve como JSON con su estado HTTP."""

    def __init__(self, status, message, details=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details


def json_body():
    """Devuelve el cuerpo JSON como diccionario o lanza 400."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "El cuerpo de la petición debe ser un objeto JSON válido")
    return data


class Validator:
    """Acumula los errores de varios campos y los devuelve juntos."""

    NAME_RE = re.compile(r"^[\w\s.'&()\-]+$", re.UNICODE)
    COUNTRY_RE = re.compile(r"^[^\W\d_]+(?:[\s\-][^\W\d_]+)*$", re.UNICODE)

    def __init__(self, data):
        self.data = data
        self.errors = {}

    def text(self, field, *, min_len=1, max_len=60, required=True, pattern=None, label=None):
        label = label or field
        if field not in self.data or self.data[field] is None:
            if required:
                self.errors[field] = f"El campo '{label}' es obligatorio"
            return None
        value = self.data[field]
        if not isinstance(value, str):
            self.errors[field] = f"'{label}' debe ser texto"
            return None
        value = " ".join(value.split())  # quita espacios sobrantes
        if not value:
            self.errors[field] = f"'{label}' no puede estar vacío"
            return None
        if not (min_len <= len(value) <= max_len):
            self.errors[field] = f"'{label}' debe tener entre {min_len} y {max_len} caracteres"
            return None
        if pattern is not None and not pattern.match(value):
            self.errors[field] = f"'{label}' contiene caracteres no permitidos"
            return None
        return value

    def integer(self, field, *, min_value=None, max_value=None, required=True, default=None, label=None):
        label = label or field
        if field not in self.data or self.data[field] is None:
            if required:
                self.errors[field] = f"El campo '{label}' es obligatorio"
            return default
        value = self.data[field]
        # bool es subclase de int en Python: se rechaza explícitamente
        if isinstance(value, bool) or not isinstance(value, int):
            self.errors[field] = f"'{label}' debe ser un número entero"
            return None
        if min_value is not None and value < min_value:
            self.errors[field] = f"'{label}' debe ser mayor o igual a {min_value}"
            return None
        if max_value is not None and value > max_value:
            self.errors[field] = f"'{label}' debe ser menor o igual a {max_value}"
            return None
        return value

    def boolean(self, field, *, default=False):
        if field not in self.data or self.data[field] is None:
            return default
        value = self.data[field]
        if not isinstance(value, bool):
            self.errors[field] = f"'{field}' debe ser true o false"
            return default
        return value

    def add(self, field, message):
        self.errors[field] = message

    def check(self):
        if self.errors:
            raise ApiError(400, "Datos inválidos", self.errors)


def query_int(name, *, min_value, max_value, default=None):
    """Lee un parámetro entero de la URL (?name=)."""
    raw = request.args.get(name)
    if raw is None or raw.strip() == "":
        return default
    if not re.fullmatch(r"-?\d+", raw.strip()):
        raise ApiError(400, "Datos inválidos", {name: f"'{name}' debe ser un número entero"})
    value = int(raw)
    if not (min_value <= value <= max_value):
        raise ApiError(400, "Datos inválidos", {name: f"'{name}' debe estar entre {min_value} y {max_value}"})
    return value


def query_text(name, *, max_len=60):
    raw = request.args.get(name)
    if raw is None:
        return None
    value = " ".join(raw.split())
    if not value:
        return None
    if len(value) > max_len:
        raise ApiError(400, "Datos inválidos", {name: f"'{name}' admite máximo {max_len} caracteres"})
    return value


def query_bool(name, default=False):
    raw = request.args.get(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in ("1", "true", "si", "sí", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    raise ApiError(400, "Datos inválidos", {name: f"'{name}' debe ser true o false"})

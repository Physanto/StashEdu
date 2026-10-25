import re
from datetime import date

from flask import request

from app.errors import ErrorAPI
from app.extensions import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def obtener_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ErrorAPI("El cuerpo de la petición debe ser un objeto JSON válido.", 400)
    return datos


def validar_requeridos(datos, campos):
    faltantes = [
        c
        for c in campos
        if datos.get(c) is None or (isinstance(datos[c], str) and not datos[c].strip())
    ]
    if faltantes:
        raise ErrorAPI("Faltan campos obligatorios.", 400, {"campos": faltantes})


def validar_opcion(valor, opciones, campo):
    if valor not in opciones:
        raise ErrorAPI(
            f"Valor inválido para '{campo}'.", 400, {"permitidos": list(opciones)}
        )


def validar_email(email):
    if not isinstance(email, str) or not EMAIL_RE.match(email):
        raise ErrorAPI("El email no tiene un formato válido.", 400)


def validar_textos(datos, limites, requeridos):
    """Valida tipos, valores nulos y longitudes de los campos de texto."""
    for campo, limite in limites.items():
        if campo not in datos:
            continue
        valor = datos[campo]
        if valor is None and campo not in requeridos:
            continue
        if not isinstance(valor, str):
            raise ErrorAPI(f"El campo '{campo}' debe ser texto.", 400)
        valor = valor.strip()
        if not valor and campo in requeridos:
            raise ErrorAPI(f"El campo '{campo}' no puede estar vacío.", 400)
        if limite is not None and len(valor) > limite:
            raise ErrorAPI(
                f"El campo '{campo}' admite máximo {limite} caracteres.", 400
            )
        # Los opcionales vacíos se guardan como NULL, incluida numero_serie.
        datos[campo] = valor or None


def filtro_opcion(nombre, opciones):
    """Lee ?nombre=valor y exige que sea una de las opciones; None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    validar_opcion(valor, opciones, nombre)
    return valor


def filtro_entero(nombre):
    """Lee ?nombre=123 como entero; None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    try:
        return int(valor)
    except ValueError:
        raise ErrorAPI(f"El filtro '{nombre}' debe ser un número entero.", 400)


def filtro_booleano(nombre):
    """Lee ?nombre=true|false (o 1|0); None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    if valor.lower() in ("true", "1"):
        return True
    if valor.lower() in ("false", "0"):
        return False
    raise ErrorAPI(f"El filtro '{nombre}' debe ser true o false.", 400)


def filtro_fecha(nombre):
    """Lee ?nombre=AAAA-MM-DD como fecha; None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ErrorAPI(f"El filtro '{nombre}' debe ser una fecha AAAA-MM-DD.", 400)


def paginar(consulta, serializar):
    """Pagina una consulta select() y devuelve {'data': [...], 'meta': {...}}."""
    pagina = max(request.args.get("page", 1, type=int), 1)
    por_pagina = min(max(request.args.get("per_page", 10, type=int), 1), 100)
    resultado = db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)
    return {
        "data": [serializar(item) for item in resultado.items],
        "meta": {
            "page": resultado.page,
            "per_page": resultado.per_page,
            "total": resultado.total,
            "pages": resultado.pages,
        },
    }

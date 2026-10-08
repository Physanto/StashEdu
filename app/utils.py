import re

from flask import request

from app.errors import ErrorAPI
from app.extensions import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def obtener_json(campos=None, no_vacio=False):
    if not request.is_json:
        raise ErrorAPI("Content-Type debe ser application/json.", 415)
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ErrorAPI("El cuerpo de la petición debe ser un objeto JSON válido.", 400)
    if campos is not None:
        desconocidos = sorted(set(datos) - set(campos))
        if desconocidos:
            raise ErrorAPI("Hay campos no permitidos.", 400, {"campos": desconocidos})
    if no_vacio and not datos:
        raise ErrorAPI("Debe enviar al menos un campo editable.")
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
    if not isinstance(email, str) or not EMAIL_RE.fullmatch(email):
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
        try:
            encoded = valor.encode("utf-8")
        except UnicodeError:
            raise ErrorAPI(f"El campo '{campo}' contiene texto Unicode inválido.")
        if "\x00" in valor or len(encoded) > 65535:
            raise ErrorAPI(
                f"El campo '{campo}' contiene texto inválido o demasiado largo."
            )
        if not valor and campo in requeridos:
            raise ErrorAPI(f"El campo '{campo}' no puede estar vacío.", 400)
        if limite is not None and len(valor) > limite:
            raise ErrorAPI(
                f"El campo '{campo}' admite máximo {limite} caracteres.", 400
            )
        # Los opcionales vacíos se guardan como NULL, incluida numero_serie.
        datos[campo] = valor or None


def paginar(consulta, serializar):
    """Pagina una consulta select() y devuelve {'data': [...], 'meta': {...}}."""
    pagina = _entero_query("page", 1)
    por_pagina = _entero_query("per_page", 10, 100)
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


def _entero_query(campo, defecto, maximo=None):
    valor = request.args.get(campo)
    if valor is None:
        return defecto
    if not re.fullmatch(r"[0-9]{1,10}", valor):
        raise ErrorAPI(f"'{campo}' debe ser un entero positivo.")
    numero = int(valor)
    if numero < 1 or (maximo is not None and numero > maximo):
        raise ErrorAPI(f"'{campo}' está fuera del rango permitido.")
    return numero


def validar_parametros():
    if not request.endpoint or not request.endpoint.startswith(
        ("usuarios.", "activos.", "prestamos.", "auth.", "health.")
    ):
        return
    permitidos = (
        {"page", "per_page"}
        if request.endpoint
        in (
            "usuarios.listar_usuarios",
            "activos.listar_activos",
            "prestamos.listar_prestamos",
        )
        else set()
    )
    desconocidos = sorted(set(request.args) - permitidos)
    if desconocidos:
        raise ErrorAPI(
            "Parámetros de consulta no permitidos.", detalles={"campos": desconocidos}
        )
    if any(len(request.args.getlist(campo)) != 1 for campo in request.args):
        raise ErrorAPI("No se permiten parámetros de consulta repetidos.")
    if any(
        type(valor) is int and valor < 1 for valor in (request.view_args or {}).values()
    ):
        raise ErrorAPI("Los identificadores deben ser enteros positivos.")

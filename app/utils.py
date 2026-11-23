import re
from datetime import date

from flask import current_app, request

from app.errors import ErrorAPI
from app.extensions import db

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
FECHA_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
ENTERO_RE = re.compile(r"[0-9]{1,10}")
# Mayor valor de una columna INT de MySQL: un id más grande no puede existir.
MAX_ID = 2_147_483_647
MAX_POR_PAGINA = 100
PAGINACION = ("page", "per_page")
FILTROS_HISTORIAL = (*PAGINACION, "estado", "desde", "hasta")


# ---------------------------------------------------------------------------
# Cuerpo de la petición
# ---------------------------------------------------------------------------
def obtener_json(campos=None, no_vacio=False):
    """Lee el cuerpo como objeto JSON.

    - Sin Content-Type: application/json → 415.
    - JSON mal escrito o que no es un objeto → 400.
    - `campos`: si se indica, cualquier otro campo → 400 (no se ignora en silencio).
    - `no_vacio`: un PATCH sin campos no tiene nada que cambiar → 400.
    """
    if not request.is_json:
        raise ErrorAPI("El Content-Type debe ser application/json.", 415)
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ErrorAPI("El cuerpo de la petición debe ser un objeto JSON válido.", 400)
    if campos is not None:
        desconocidos = sorted(set(datos) - set(campos))
        if desconocidos:
            raise ErrorAPI(
                "Hay campos no permitidos.",
                400,
                {"campos": desconocidos, "permitidos": list(campos)},
            )
    if no_vacio and not datos:
        raise ErrorAPI("Envíe al menos un campo para modificar.", 400)
    return datos


def validar_requeridos(datos, campos):
    faltantes = [
        c
        for c in campos
        if datos.get(c) is None or (isinstance(datos[c], str) and not datos[c].strip())
    ]
    if faltantes:
        raise ErrorAPI("Faltan campos obligatorios.", 400, {"campos": faltantes})


def entero_positivo(valor, campo):
    # bool es subclase de int en Python: se descarta de forma explícita.
    if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= MAX_ID:
        raise ErrorAPI(f"El campo '{campo}' debe ser un entero positivo.", 400)
    return valor


def validar_opcion(valor, opciones, campo):
    if valor not in opciones:
        raise ErrorAPI(
            f"Valor inválido para '{campo}'.", 400, {"permitidos": list(opciones)}
        )


def normalizar_email(datos):
    """Guarda y busca los correos en minúsculas: Ana@X.com y ana@x.com son el mismo."""
    if isinstance(datos.get("email"), str):
        datos["email"] = datos["email"].strip().lower()


def validar_email(email):
    if not isinstance(email, str) or not EMAIL_RE.fullmatch(email):
        raise ErrorAPI("El email no tiene un formato válido.", 400)


def validar_textos(datos, limites, requeridos):
    """Valida tipos, valores nulos, contenido y longitudes de los campos de texto."""
    for campo, limite in limites.items():
        if campo not in datos:
            continue
        valor = datos[campo]
        if valor is None and campo not in requeridos:
            continue
        if not isinstance(valor, str):
            raise ErrorAPI(f"El campo '{campo}' debe ser texto.", 400)
        valor = valor.strip()
        # JSON permite "\u0000" y mitades de emoji sueltas ("\ud800"): la BD no
        # puede guardarlas, así que se rechazan aquí como error del cliente.
        try:
            valor.encode("utf-8")
        except UnicodeEncodeError:
            raise ErrorAPI(f"El campo '{campo}' contiene texto Unicode inválido.", 400)
        if "\x00" in valor:
            raise ErrorAPI(f"El campo '{campo}' contiene caracteres no permitidos.", 400)
        if not valor and campo in requeridos:
            raise ErrorAPI(f"El campo '{campo}' no puede estar vacío.", 400)
        if limite is not None and len(valor) > limite:
            raise ErrorAPI(
                f"El campo '{campo}' admite máximo {limite} caracteres.", 400
            )
        # Los opcionales vacíos se guardan como NULL, incluida numero_serie.
        datos[campo] = valor or None


# ---------------------------------------------------------------------------
# Parámetros de la URL (?clave=valor)
# ---------------------------------------------------------------------------
def acepta_parametros(*nombres):
    """Declara qué parámetros de consulta admite una ruta; los demás → 400.

    Va debajo del decorador de la ruta:
        @bp.get("")
        @acepta_parametros("page", "per_page", "estado")
        def listar(): ...
    """

    def decorador(vista):
        vista.parametros_permitidos = tuple(nombres)
        return vista

    return decorador


def parametros_de(endpoint):
    """Parámetros de consulta que admite un endpoint (lo usa también OpenAPI)."""
    vista = current_app.view_functions.get(endpoint)
    return getattr(vista, "parametros_permitidos", ())


def validar_parametros():
    """before_request de los blueprints de la API (después de autenticar)."""
    permitidos = parametros_de(request.endpoint)
    desconocidos = sorted(set(request.args) - set(permitidos))
    if desconocidos:
        raise ErrorAPI(
            "Parámetros de consulta no permitidos.",
            400,
            {"parametros": desconocidos, "permitidos": list(permitidos)},
        )
    repetidos = sorted(c for c in request.args if len(request.args.getlist(c)) > 1)
    if repetidos:
        raise ErrorAPI(
            "No se permiten parámetros de consulta repetidos.",
            400,
            {"parametros": repetidos},
        )
    # Los ids de la ruta (/usuarios/<id>) deben estar en el rango de un INT.
    for valor in (request.view_args or {}).values():
        if type(valor) is int and not 1 <= valor <= MAX_ID:
            raise ErrorAPI("Los identificadores deben ser enteros positivos.", 400)


def filtro_opcion(nombre, opciones):
    """Lee ?nombre=valor y exige que sea una de las opciones; None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    validar_opcion(valor, opciones, nombre)
    return valor


def filtro_entero(nombre, defecto=None, maximo=MAX_ID):
    """Lee ?nombre=123 como entero positivo; `defecto` si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return defecto
    if not ENTERO_RE.fullmatch(valor) or not 1 <= int(valor) <= maximo:
        raise ErrorAPI(
            f"El parámetro '{nombre}' debe ser un entero entre 1 y {maximo}.", 400
        )
    return int(valor)


def filtro_booleano(nombre):
    """Lee ?nombre=true|false (o 1|0); None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    if valor.lower() in ("true", "1"):
        return True
    if valor.lower() in ("false", "0"):
        return False
    raise ErrorAPI(f"El parámetro '{nombre}' debe ser true o false.", 400)


def filtro_fecha(nombre):
    """Lee ?nombre=AAAA-MM-DD como fecha; None si no se envió."""
    valor = request.args.get(nombre)
    if valor is None:
        return None
    try:
        # fromisoformat acepta otros formatos (20261001, 2026-W40...): se exige el exacto.
        if not FECHA_RE.fullmatch(valor):
            raise ValueError
        return date.fromisoformat(valor)
    except ValueError:
        raise ErrorAPI(f"El parámetro '{nombre}' debe ser una fecha AAAA-MM-DD.", 400)


def paginar(consulta, serializar):
    """Pagina una consulta select() y devuelve {'data': [...], 'meta': {...}}."""
    pagina = filtro_entero("page", 1)
    por_pagina = filtro_entero("per_page", 10, MAX_POR_PAGINA)
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

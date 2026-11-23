"""Contrato OpenAPI 3.0.3 de la API, servido en /openapi.json y visible en /docs.

El contrato se arma con funciones pequeñas para no repetir lo mismo en cada ruta.
tests/test_openapi.py comprueba que documente exactamente las rutas y los
parámetros de consulta que la aplicación implementa.
"""

from copy import deepcopy

from flask import Blueprint, jsonify

from app.models.activo import CATEGORIAS, ESTADOS, ESTADOS_EDITABLES
from app.models.prestamo import ESTADOS_PRESTAMO, FILTROS_ESTADO
from app.models.rol import ROL_ADMIN, ROL_CONSULTA, ROL_OPERADOR
from app.utils import MAX_ID, MAX_POR_PAGINA

docs_bp = Blueprint("docs", __name__)

ROLES = (ROL_ADMIN, ROL_OPERADOR, ROL_CONSULTA)
TODOS = "Roles: admin, operador y consulta."
ESCRITURA = "Roles: admin y operador."
SOLO_ADMIN = "Rol: solo admin."


# ---------------------------------------------------------------------------
# Piezas de esquema
# ---------------------------------------------------------------------------
def ref(nombre):
    return {"$ref": f"#/components/schemas/{nombre}"}


def texto(maximo=None, *, nulo=False, **extra):
    esquema = {"type": "string", **extra}
    if maximo is not None:
        esquema["maxLength"] = maximo
    if nulo:
        esquema["nullable"] = True
    return esquema


def entero(**extra):
    return {"type": "integer", "minimum": 1, "maximum": MAX_ID, **extra}


def objeto(propiedades, requeridos=(), **extra):
    esquema = {
        "type": "object",
        "properties": propiedades,
        "additionalProperties": False,
        **extra,
    }
    if requeridos:
        esquema["required"] = list(requeridos)
    return esquema


FECHA_HORA = texto(format="date-time", readOnly=True, example="2026-11-23T15:00:00Z")
TIMESTAMPS = {"created_at": FECHA_HORA, "updated_at": FECHA_HORA}
PASSWORD = texto(
    128,
    minLength=12,
    writeOnly=True,
    description="Entre 12 y 128 caracteres; se conserva exacta (incluidos los espacios).",
    example="Clave segura 2026",
)

CAMPOS_USUARIO = {
    "nombre_completo": texto(120, minLength=1, example="Ana Pérez"),
    "documento": texto(20, minLength=1, example="1000123456"),
    "email": texto(
        120,
        format="email",
        description="Se recortan los espacios y se guarda en minúsculas.",
        example="ana@stashedu.edu",
    ),
    "telefono": texto(20, nulo=True, example="3001234567"),
    "tipo_usuario_id": entero(description="Ver GET /api/v1/tipos-usuario.", example=1),
    "habilitado": {"type": "boolean", "example": True},
}
REQUERIDOS_USUARIO = ("nombre_completo", "documento", "email", "tipo_usuario_id")

CAMPOS_ACTIVO = {
    "codigo_inventario": texto(30, minLength=1, example="PORT-007"),
    "nombre": texto(100, minLength=1, example="Portátil Lenovo"),
    "categoria": {"type": "string", "enum": list(CATEGORIAS), "example": "portatil"},
    "marca": texto(60, nulo=True, example="Lenovo"),
    "modelo": texto(60, nulo=True, example="ThinkPad E14"),
    "numero_serie": texto(60, nulo=True, example="SN-123456"),
    "estado": {
        "type": "string",
        "enum": list(ESTADOS_EDITABLES),
        "description": "'prestado' solo lo asignan los préstamos.",
        "example": "disponible",
    },
}
REQUERIDOS_ACTIVO = ("codigo_inventario", "nombre", "categoria")

RESUMEN_PERSONA = objeto(
    {"id": entero(), "nombre_completo": texto(example="Laura Ríos")},
    ("id", "nombre_completo"),
)


def schemas():
    usuario = {"id": entero(readOnly=True), **deepcopy(CAMPOS_USUARIO)}
    usuario.update(
        {
            "tipo_usuario": texto(readOnly=True, example="estudiante"),
            "rol_id": entero(nullable=True, readOnly=True, example=None),
            "rol": {
                "type": "string",
                "enum": list(ROLES),
                "nullable": True,
                "readOnly": True,
                "description": "null si la persona no tiene cuenta (solo pide prestado).",
            },
            **TIMESTAMPS,
        }
    )
    activo = {"id": entero(readOnly=True), **deepcopy(CAMPOS_ACTIVO)}
    activo["estado"] = {"type": "string", "enum": list(ESTADOS), "readOnly": True}
    activo.update(TIMESTAMPS)

    def pagina(modelo):
        return objeto(
            {"data": {"type": "array", "items": ref(modelo)}, "meta": ref("Meta")},
            ("data", "meta"),
        )

    return {
        "Error": {
            "type": "object",
            "properties": {
                "error": texto(example="Faltan campos obligatorios."),
                "detalles": {
                    "type": "object",
                    "additionalProperties": True,
                    "example": {"campos": ["email"]},
                },
            },
            "required": ["error"],
        },
        "Health": objeto(
            {
                "status": {"type": "string", "enum": ["ok", "error"]},
                "database": {"type": "string", "enum": ["connected", "unreachable"]},
            },
            ("status", "database"),
        ),
        "Meta": objeto(
            {
                "page": entero(example=1),
                "per_page": entero(maximum=MAX_POR_PAGINA, example=10),
                "total": {"type": "integer", "minimum": 0, "example": 1},
                "pages": {"type": "integer", "minimum": 0, "example": 1},
            },
            ("page", "per_page", "total", "pages"),
        ),
        "TipoUsuario": objeto(
            {
                "id": entero(),
                "codigo": texto(example="estudiante"),
                "descripcion": texto(example="Estudiante"),
                "max_prestamos_activos": entero(example=1),
                "dias_max_prestamo": entero(example=3),
            },
            ("id", "codigo", "descripcion", "max_prestamos_activos", "dias_max_prestamo"),
        ),
        "Rol": objeto(
            {
                "id": entero(),
                "codigo": {"type": "string", "enum": list(ROLES)},
                "descripcion": texto(example="Entrega y recibe activos"),
            },
            ("id", "codigo", "descripcion"),
        ),
        "ListaTiposUsuario": objeto(
            {"data": {"type": "array", "items": ref("TipoUsuario")}}, ("data",)
        ),
        "ListaRoles": objeto({"data": {"type": "array", "items": ref("Rol")}}, ("data",)),
        # --- Autenticación ---
        "Registro": objeto(
            {
                "usuario_id": entero(description="Persona que ya existe en /usuarios."),
                "password": PASSWORD,
                "rol_id": entero(description="Ver GET /api/v1/roles.", example=2),
            },
            ("usuario_id", "password", "rol_id"),
        ),
        "Login": objeto(
            {"email": CAMPOS_USUARIO["email"], "password": PASSWORD},
            ("email", "password"),
        ),
        "Token": objeto(
            {
                "access_token": texto(description="JWT firmado con HS256."),
                "token_type": {"type": "string", "enum": ["Bearer"]},
                "expires_in": entero(description="Segundos de validez.", example=3600),
                "usuario": ref("Usuario"),
            },
            ("access_token", "token_type", "expires_in", "usuario"),
        ),
        # --- Usuarios ---
        "Usuario": objeto(usuario, ("id", *REQUERIDOS_USUARIO, "habilitado")),
        "UsuarioCrear": objeto(deepcopy(CAMPOS_USUARIO), REQUERIDOS_USUARIO),
        "UsuarioPatch": objeto(deepcopy(CAMPOS_USUARIO), minProperties=1),
        "PaginaUsuarios": pagina("Usuario"),
        # --- Activos ---
        "Activo": objeto(activo, ("id", *REQUERIDOS_ACTIVO, "estado")),
        "ActivoCrear": objeto(deepcopy(CAMPOS_ACTIVO), REQUERIDOS_ACTIVO),
        "ActivoPatch": objeto(deepcopy(CAMPOS_ACTIVO), minProperties=1),
        "PaginaActivos": pagina("Activo"),
        # --- Préstamos ---
        "Prestamo": objeto(
            {
                "id": entero(readOnly=True),
                "usuario": deepcopy(RESUMEN_PERSONA),
                "activo": objeto(
                    {
                        "id": entero(),
                        "codigo_inventario": texto(example="PORT-007"),
                        "nombre": texto(example="Portátil Lenovo"),
                    },
                    ("id", "codigo_inventario", "nombre"),
                ),
                "fecha_prestamo": FECHA_HORA,
                "fecha_vencimiento": FECHA_HORA,
                "fecha_devolucion": {**FECHA_HORA, "nullable": True},
                "estado": {
                    "type": "string",
                    "enum": list(ESTADOS_PRESTAMO),
                    "description": "Se calcula con las fechas; no se guarda.",
                },
                "dias_retraso": {"type": "integer", "minimum": 0, "example": 0},
                "observaciones_entrega": texto(nulo=True),
                "observaciones_devolucion": texto(nulo=True),
                "entregado_por": {
                    **deepcopy(RESUMEN_PERSONA),
                    "nullable": True,
                    "description": "Cuenta que registró el préstamo (sale del token).",
                },
                "recibido_por": {
                    **deepcopy(RESUMEN_PERSONA),
                    "nullable": True,
                    "description": "Cuenta que registró la devolución (sale del token).",
                },
                **TIMESTAMPS,
            },
            ("id", "usuario", "activo", "fecha_prestamo", "fecha_vencimiento", "estado"),
        ),
        "PrestamoCrear": objeto(
            {
                "usuario_id": entero(example=1),
                "activo_id": entero(example=1),
                "dias": entero(
                    description="Opcional; por defecto el máximo del tipo de usuario.",
                    example=3,
                ),
                "observaciones_entrega": texto(1000, nulo=True, example="Con cargador"),
            },
            ("usuario_id", "activo_id"),
        ),
        "Devolucion": objeto(
            {"observaciones_devolucion": texto(1000, nulo=True, example="Sin daños")}
        ),
        "PaginaPrestamos": pagina("Prestamo"),
    }


# ---------------------------------------------------------------------------
# Parámetros de consulta (los mismos nombres que declara @acepta_parametros)
# ---------------------------------------------------------------------------
PARAMETROS = {
    "page": {"description": "Número de página.", "schema": entero(default=1)},
    "per_page": {
        "description": f"Resultados por página (1 a {MAX_POR_PAGINA}).",
        "schema": entero(maximum=MAX_POR_PAGINA, default=10),
    },
    "estado_prestamo": {
        "name": "estado",
        "description": "'pendiente' agrupa activo y vencido.",
        "schema": {"type": "string", "enum": list(FILTROS_ESTADO)},
    },
    "estado_activo": {
        "name": "estado",
        "schema": {"type": "string", "enum": list(ESTADOS)},
    },
    "categoria": {"schema": {"type": "string", "enum": list(CATEGORIAS)}},
    "desde": {
        "description": "Préstamos desde esta fecha (UTC, AAAA-MM-DD).",
        "schema": {"type": "string", "format": "date"},
    },
    "hasta": {
        "description": "Préstamos hasta esta fecha, incluida (UTC, AAAA-MM-DD).",
        "schema": {"type": "string", "format": "date"},
    },
    "usuario_id": {"schema": entero()},
    "activo_id": {"schema": entero()},
    "tipo_usuario_id": {"schema": entero()},
    "habilitado": {"schema": {"type": "boolean"}},
}


def parametros(*claves):
    resultado = []
    for clave in claves:
        definicion = deepcopy(PARAMETROS[clave])
        resultado.append({"name": definicion.pop("name", clave), "in": "query", **definicion})
    return resultado


def id_en_ruta(nombre):
    return [{"name": nombre, "in": "path", "required": True, "schema": entero()}]


HISTORIAL = ("page", "per_page", "estado_prestamo", "desde", "hasta")


# ---------------------------------------------------------------------------
# Respuestas y operaciones
# ---------------------------------------------------------------------------
ERRORES = {
    400: ("Datos o parámetros inválidos.", "Faltan campos obligatorios."),
    401: ("Sin token, token inválido o vencido.", "Se requiere un token Bearer válido."),
    403: ("El rol de la cuenta no permite la operación.", "No tienes permiso para realizar esta operación."),
    404: ("El recurso no existe.", "Recurso no encontrado."),
    409: ("Choca con el estado actual de los datos.", "El activo no está disponible."),
    413: ("El cuerpo supera 64 KB.", "El cuerpo de la petición supera el tamaño máximo permitido."),
    415: ("El cuerpo no es application/json.", "El Content-Type debe ser application/json."),
    500: ("Error inesperado del servidor.", "Error interno del servidor."),
    503: ("La base de datos no está disponible.", "La base de datos no está disponible."),
}


def respuesta(descripcion, modelo=None):
    resultado = {"description": descripcion}
    if modelo:
        resultado["content"] = {"application/json": {"schema": ref(modelo)}}
    return resultado


def respuesta_error(codigo):
    descripcion, ejemplo = ERRORES[codigo]
    resultado = respuesta(descripcion, "Error")
    resultado["content"]["application/json"]["example"] = {"error": ejemplo}
    return resultado


def operacion(
    operation_id,
    tag,
    resumen,
    descripcion,
    modelo=None,
    *,
    estado=200,
    cuerpo=None,
    cuerpo_opcional=False,
    parametros_ruta=(),
    parametros_query=(),
    publica=False,
    errores=(),
):
    codigos = {400, 500, 503, *errores}
    if not publica:
        codigos.add(401)
    if cuerpo:
        codigos.update((413, 415))
    exito = "Sin contenido." if estado == 204 else "Operación completada."
    resultado = {
        "operationId": operation_id,
        "tags": [tag],
        "summary": resumen,
        "description": descripcion,
        "responses": {
            str(estado): respuesta(exito, modelo),
            **{str(c): respuesta_error(c) for c in sorted(codigos)},
        },
    }
    if publica:
        resultado["security"] = []
    lista = [*parametros_ruta, *parametros_query]
    if lista:
        resultado["parameters"] = deepcopy(lista)
    if cuerpo:
        resultado["requestBody"] = {
            "required": not cuerpo_opcional,
            "description": "Objeto JSON (máximo 64 KB). Los campos no documentados se rechazan con 400.",
            "content": {"application/json": {"schema": ref(cuerpo)}},
        }
    return resultado


def _crud(ruta, nombre, modelo, tag, id_nombre, *, filtros, errores_borrar, desc_borrar):
    coleccion = f"/api/v1/{ruta}"
    item = f"{coleccion}/{{{id_nombre}}}"
    return {
        coleccion: {
            "get": operacion(
                f"listar_{ruta}", tag, f"Listar {ruta}",
                f"Paginado y ordenado por id. {TODOS}",
                f"Pagina{modelo}s",
                parametros_query=parametros("page", "per_page", *filtros),
            ),
            "post": operacion(
                f"crear_{nombre}", tag, f"Crear {nombre}", ESCRITURA, modelo,
                estado=201, cuerpo=f"{modelo}Crear", errores=(403, 409),
            ),
        },
        item: {
            "get": operacion(
                f"obtener_{nombre}", tag, f"Obtener {nombre}", TODOS, modelo,
                parametros_ruta=id_en_ruta(id_nombre), errores=(404,),
            ),
            "put": operacion(
                f"reemplazar_{nombre}", tag, f"Reemplazar {nombre}",
                f"Exige los campos obligatorios; los opcionales omitidos se conservan. {ESCRITURA}",
                modelo, cuerpo=f"{modelo}Crear", parametros_ruta=id_en_ruta(id_nombre),
                errores=(403, 404, 409),
            ),
            "patch": operacion(
                f"modificar_{nombre}", tag, f"Modificar {nombre}",
                f"Cambia solo los campos enviados (al menos uno). {ESCRITURA}",
                modelo, cuerpo=f"{modelo}Patch", parametros_ruta=id_en_ruta(id_nombre),
                errores=(403, 404, 409),
            ),
            "delete": operacion(
                f"borrar_{nombre}", tag, f"Dar de baja {nombre}",
                f"{desc_borrar} {SOLO_ADMIN}", estado=204,
                parametros_ruta=id_en_ruta(id_nombre), errores=errores_borrar,
            ),
        },
        f"{item}/prestamos": {
            "get": operacion(
                f"historial_{nombre}", tag, f"Historial de préstamos del {nombre}",
                f"Del más reciente al más antiguo. {TODOS}", "PaginaPrestamos",
                parametros_ruta=id_en_ruta(id_nombre),
                parametros_query=parametros(*HISTORIAL), errores=(404,),
            )
        },
    }


def build_spec():
    paths = {
        "/api/v1/health": {
            "get": {
                "operationId": "health",
                "tags": ["Sistema"],
                "summary": "Comprobar la conexión con la base de datos",
                "description": "Público.",
                "security": [],
                "responses": {
                    "200": respuesta("Base de datos conectada.", "Health"),
                    "400": respuesta_error(400),
                    "503": respuesta("Base de datos inaccesible.", "Health"),
                },
            }
        },
        "/api/v1/tipos-usuario": {
            "get": operacion(
                "listar_tipos_usuario", "Catálogos", "Tipos de usuario",
                f"Límites de préstamo de cada tipo. {TODOS}", "ListaTiposUsuario",
            )
        },
        "/api/v1/roles": {
            "get": operacion(
                "listar_roles", "Catálogos", "Roles",
                f"Valores válidos de rol_id para registrar cuentas. {TODOS}", "ListaRoles",
            )
        },
        "/api/v1/auth/register": {
            "post": operacion(
                "registrar_cuenta", "Autenticación", "Registrar una cuenta",
                "Da rol y contraseña a una persona que ya existe en /usuarios. "
                f"{SOLO_ADMIN}",
                "Usuario", estado=201, cuerpo="Registro", errores=(403, 404, 409),
            )
        },
        "/api/v1/auth/login": {
            "post": operacion(
                "login", "Autenticación", "Iniciar sesión",
                "Público. Devuelve un JWT para el header Authorization: Bearer <token>. "
                "Email o contraseña incorrectos reciben el mismo 401.",
                "Token", cuerpo="Login", publica=True, errores=(401,),
            )
        },
        "/api/v1/auth/me": {
            "get": operacion(
                "perfil", "Autenticación", "Cuenta autenticada",
                f"Datos de la cuenta dueña del token. {TODOS}", "Usuario",
            )
        },
    }
    paths.update(
        _crud(
            "usuarios", "usuario", "Usuario", "Usuarios", "usuario_id",
            filtros=("tipo_usuario_id", "habilitado"),
            errores_borrar=(403, 404, 409),
            desc_borrar="Baja lógica (habilitado = false); 409 si tiene préstamos sin devolver.",
        )
    )
    paths.update(
        _crud(
            "activos", "activo", "Activo", "Activos", "activo_id",
            filtros=("estado_activo", "categoria"),
            errores_borrar=(403, 404, 409),
            desc_borrar="Baja lógica (estado = 'baja'); 409 si está prestado.",
        )
    )
    paths["/api/v1/prestamos"] = {
        "get": operacion(
            "listar_prestamos", "Préstamos", "Listar préstamos",
            f"Del más reciente al más antiguo. {TODOS}", "PaginaPrestamos",
            parametros_query=parametros(*HISTORIAL, "usuario_id", "activo_id"),
        ),
        "post": operacion(
            "crear_prestamo", "Préstamos", "Crear préstamo",
            "Reserva el activo y calcula el vencimiento según el tipo de usuario. "
            f"entregado_por se toma del token. {ESCRITURA}",
            "Prestamo", estado=201, cuerpo="PrestamoCrear", errores=(403, 404, 409),
        ),
    }
    paths["/api/v1/prestamos/{prestamo_id}"] = {
        "get": operacion(
            "obtener_prestamo", "Préstamos", "Obtener préstamo", TODOS, "Prestamo",
            parametros_ruta=id_en_ruta("prestamo_id"), errores=(404,),
        )
    }
    paths["/api/v1/prestamos/{prestamo_id}/devolucion"] = {
        "post": operacion(
            "registrar_devolucion", "Préstamos", "Registrar devolución",
            "El activo vuelve a 'disponible'; la fecha la pone el servidor y "
            f"recibido_por se toma del token. El cuerpo es opcional. {ESCRITURA}",
            "Prestamo", cuerpo="Devolucion", cuerpo_opcional=True,
            parametros_ruta=id_en_ruta("prestamo_id"), errores=(403, 404, 409),
        )
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "StashEdu API",
            "version": "1.0.0",
            "description": (
                "API REST para el préstamo de activos tecnológicos de una institución educativa.\n\n"
                "**Autenticación:** `POST /api/v1/auth/login` devuelve un JWT (HS256, 1 hora). "
                "Pulse **Authorize** y pegue el token. Solo `health`, `login` y esta documentación son públicos.\n\n"
                "**Roles:** admin = todo · operador = ver todo, crear/editar usuarios y activos, "
                "crear y devolver préstamos · consulta = solo GET. Sin token → 401; sin permiso → 403.\n\n"
                "**Validación:** los cuerpos deben ser JSON (`Content-Type: application/json`, máximo 64 KB); "
                "los campos y parámetros de consulta no documentados se rechazan con 400.\n\n"
                "**Errores:** siempre `{\"error\": \"mensaje\", \"detalles\": {...}}`. "
                "Fechas en UTC con sufijo Z."
            ),
        },
        "servers": [{"url": "/", "description": "El mismo servidor que publica esta documentación"}],
        "tags": [
            {"name": n}
            for n in ("Sistema", "Autenticación", "Catálogos", "Usuarios", "Activos", "Préstamos")
        ],
        "security": [{"BearerAuth": []}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Token obtenido en POST /api/v1/auth/login.",
                }
            },
            "schemas": schemas(),
        },
    }


@docs_bp.get("/openapi.json")
def openapi():
    respuesta_json = jsonify(build_spec())
    # Sin caché: el contrato debe reflejar siempre la versión del servidor.
    respuesta_json.headers["Cache-Control"] = "no-store"
    return respuesta_json


def registrar_documentacion(app):
    """Publica /openapi.json y Swagger UI en /docs (archivos locales, sin CDN)."""
    from flask_swagger_ui import get_swaggerui_blueprint

    app.register_blueprint(docs_bp)
    app.register_blueprint(
        get_swaggerui_blueprint(
            "/docs",
            "/openapi.json",
            config={
                "app_name": "StashEdu API",
                "validatorUrl": None,
                "persistAuthorization": False,
                "docExpansion": "list",
            },
        )
    )

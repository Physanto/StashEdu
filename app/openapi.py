"""Contrato OpenAPI de las rutas públicas y autenticadas de StashEdu."""

from copy import deepcopy

from flask import Blueprint, jsonify

from app.models.activo import CATEGORIAS, ESTADOS_EDITABLES
from app.models.usuario import TIPOS_USUARIO

docs_bp = Blueprint("docs", __name__)


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def text(limit=None, *, nullable=False, **kwargs):
    schema = {"type": "string", **kwargs}
    if limit is not None:
        schema["maxLength"] = limit
    if nullable:
        schema["nullable"] = True
    return schema


def object_schema(properties, required=(), **kwargs):
    schema = {"type": "object", "properties": properties, "additionalProperties": False, **kwargs}
    if required:
        schema["required"] = list(required)
    return schema


ID = {"type": "integer", "minimum": 1, "example": 1}
PASSWORD = text(128, minLength=12, writeOnly=True,
                description="Se conserva exactamente, incluidos los espacios; no admite solo espacios.",
                example="Una contraseña segura 123")
TIMESTAMPS = {
    field: text(description="Fecha UTC ISO 8601; la serialización histórica no incluye sufijo de zona.",
                readOnly=True, example="2026-10-08T15:00:00.000000")
    for field in ("created_at", "updated_at")
}
USER_FIELDS = {
    "nombre_completo": text(120, minLength=1, example="Ana Pérez"),
    "documento": text(20, minLength=1, example="1000123456"),
    "email": text(120, format="email", description="Se recortan espacios y se normaliza a minúsculas.", example="ana@example.com"),
    "tipo_usuario": text(20, enum=list(TIPOS_USUARIO), description="Tipo institucional; no concede permisos de operador."),
    "telefono": text(20, nullable=True, example="3001234567"),
    "activo": {"type": "boolean", "default": True},
}
USER_REQUIRED = ("nombre_completo", "documento", "email", "tipo_usuario")
ASSET_FIELDS = {
    "codigo_inventario": text(30, minLength=1, example="INV-001"),
    "nombre": text(100, minLength=1, example="Portátil de biblioteca"),
    "categoria": text(30, enum=list(CATEGORIAS)),
    "marca": text(60, nullable=True),
    "modelo": text(60, nullable=True),
    "numero_serie": text(60, nullable=True, description="Valor único cuando no es nulo; texto vacío se convierte en null."),
    "descripcion": text(10000, nullable=True, description="Máximo 10000 caracteres y 65535 bytes UTF-8."),
    "estado": text(20, enum=list(ESTADOS_EDITABLES), default="disponible", description="El estado prestado solo se establece mediante el flujo de préstamos."),
    "fecha_adquisicion": text(nullable=True, format="date", example="2026-10-01"),
}
ASSET_REQUIRED = ("codigo_inventario", "nombre", "categoria")
LOAN_INPUT = {
    "usuario_id": deepcopy(ID),
    "activo_id": deepcopy(ID),
    "fecha_devolucion_prevista": text(format="date-time", example="2026-10-20T18:00:00-05:00",
                                     description="ISO 8601 con zona horaria; debe ser posterior al instante de creación. Se persiste en UTC."),
    "observaciones": text(1000, nullable=True),
}


def schemas():
    asset_output = deepcopy(ASSET_FIELDS)
    asset_output["estado"] = text(20, enum=[*ESTADOS_EDITABLES, "prestado"])
    register_fields = {key: deepcopy(value) for key, value in USER_FIELDS.items() if key != "activo"}
    register_fields["password"] = deepcopy(PASSWORD)
    loan_output = {
        "id": deepcopy(ID), **deepcopy(LOAN_INPUT),
        "fecha_prestamo": text(format="date-time", readOnly=True, example="2026-10-08T15:00:00Z"),
        "fecha_devolucion": text(nullable=True, format="date-time", readOnly=True),
        "estado": text(enum=["activo", "devuelto"], readOnly=True),
        "retrasado": {"type": "boolean", "readOnly": True,
                      "description": "Compara la devolución efectiva, o el momento actual, con la fecha prevista."},
        **deepcopy(TIMESTAMPS),
    }
    result = {
        "Error": object_schema({"error": text(example="Token inválido o expirado."),
                                "detalles": {"type": "object", "additionalProperties": True}}, ("error",)),
        "Health": object_schema({"status": text(enum=["ok", "error"]),
                                 "database": text(enum=["connected", "unreachable"])}, ("status", "database")),
        "Usuario": object_schema({"id": deepcopy(ID), **deepcopy(USER_FIELDS), **deepcopy(TIMESTAMPS)},
                                 ("id", *USER_FIELDS, *TIMESTAMPS)),
        "UsuarioCreate": object_schema(deepcopy(USER_FIELDS), USER_REQUIRED),
        "UsuarioReplace": object_schema(deepcopy(USER_FIELDS), USER_REQUIRED),
        "UsuarioPatch": object_schema(deepcopy(USER_FIELDS), minProperties=1),
        "Registro": object_schema(register_fields, (*USER_REQUIRED, "password")),
        "Login": object_schema({"email": deepcopy(USER_FIELDS["email"]), "password": deepcopy(PASSWORD)}, ("email", "password")),
        "Token": object_schema({"access_token": text(description="Token firmado itsdangerous, no JWT."),
                                "token_type": text(enum=["Bearer"]),
                                "expires_in": {"type": "integer", "minimum": 1, "example": 3600,
                                               "description": "Vigencia en segundos configurada por AUTH_TOKEN_MAX_AGE."},
                                "usuario": ref("Usuario")}, ("access_token", "token_type", "expires_in", "usuario")),
        "Activo": object_schema({"id": deepcopy(ID), **asset_output, **deepcopy(TIMESTAMPS)}, ("id", *asset_output, *TIMESTAMPS)),
        "ActivoCreate": object_schema(deepcopy(ASSET_FIELDS), ASSET_REQUIRED),
        "ActivoReplace": object_schema(deepcopy(ASSET_FIELDS), ASSET_REQUIRED),
        "ActivoPatch": object_schema(deepcopy(ASSET_FIELDS), minProperties=1),
        "PrestamoCreate": object_schema(deepcopy(LOAN_INPUT), ("usuario_id", "activo_id", "fecha_devolucion_prevista")),
        "Prestamo": object_schema(loan_output, tuple(loan_output)),
        "Devolucion": object_schema({}, maxProperties=0, example={}),
        "PaginationMeta": object_schema({
            "page": {"type": "integer", "minimum": 1},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
            "total": {"type": "integer", "minimum": 0},
            "pages": {"type": "integer", "minimum": 0},
        }, ("page", "per_page", "total", "pages")),
    }
    for model in ("Usuario", "Activo", "Prestamo"):
        result[f"{model}Page"] = object_schema({"data": {"type": "array", "items": ref(model)},
                                                "meta": ref("PaginationMeta")}, ("data", "meta"))
    return result


ERROR_DESCRIPTIONS = {
    400: "JSON, campos, valores o parámetros de consulta inválidos.",
    401: "Credenciales incorrectas; token ausente, inválido, expirado o revocado; usuario inactivo.",
    403: "Permiso insuficiente: se exige propietario u operador según la operación.",
    404: "El recurso solicitado no existe.",
    409: "Valor único duplicado o conflicto con las reglas de préstamo, devolución o baja lógica.",
    413: "El cuerpo excede el límite de 64 KiB.",
    415: "El cuerpo requiere Content-Type application/json.",
    500: "Error interno del servidor.",
    503: "Base de datos no disponible o SECRET_KEY sin configurar correctamente.",
}
PAGINATION = [
    {"name": "page", "in": "query", "description": "Entero positivo; valores inválidos se rechazan.",
     "schema": {"type": "integer", "minimum": 1, "default": 1}, "example": 1},
    {"name": "per_page", "in": "query", "description": "Tamaño de página entre 1 y 100.",
     "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}, "example": 10},
]


def response(description, model=None):
    result = {"description": description}
    if model:
        result["content"] = {"application/json": {"schema": ref(model)}}
    return result


def error_response(code):
    result = response(ERROR_DESCRIPTIONS[code], "Error")
    examples = {
        400: "Faltan campos obligatorios.",
        401: "Token inválido o expirado.",
        403: "Esta operación requiere un operador autorizado.",
        404: "Préstamo no encontrado.",
        409: "El activo no está disponible.",
        413: "El cuerpo de la petición excede el tamaño permitido.",
        415: "El cuerpo de la petición debe usar Content-Type application/json.",
        500: "Error interno del servidor.",
        503: "La base de datos no está disponible.",
    }
    result["content"]["application/json"]["example"] = {"error": examples[code]}
    return result


def operation(operation_id, tag, summary, description, model, *, status=200,
              body=None, parameters=(), public=False, errors=()):
    codes = {400, 500, 503, *errors}
    if not public:
        codes.add(401)
    if body:
        codes.update((413, 415))
    result = {
        "operationId": operation_id, "tags": [tag], "summary": summary, "description": description,
        "responses": {str(status): response("Operación completada." if status != 204 else "Baja lógica realizada; sin cuerpo de respuesta.", model),
                      **{str(code): error_response(code) for code in sorted(codes)}},
    }
    if public:
        result["security"] = []
    if parameters:
        result["parameters"] = deepcopy(list(parameters))
    if body:
        result["requestBody"] = {"required": True, "description": "Objeto JSON; máximo 64 KiB. Campos desconocidos se rechazan.",
                                 "content": {"application/json": {"schema": ref(body)}}}
    return result


def path_id(name):
    return [{"name": name, "in": "path", "required": True, "schema": deepcopy(ID)}]


def build_spec():
    paths = {}
    paths["/api/v1/health"] = {"get": {
        "operationId": "health", "tags": ["Sistema"], "summary": "Comprobar conexión a la base de datos",
        "security": [], "responses": {"200": response("Base de datos conectada.", "Health"),
                                       "503": response("Base de datos inaccesible.", "Health")},
    }}
    paths["/api/v1/auth/register"] = {"post": operation("register", "Autenticación", "Registrar una cuenta", "Público. Crea una cuenta activa sin permisos de operador. Rechaza id, activo, rol y password_hash.", "Usuario", status=201, body="Registro", public=True, errors=(409,))}
    paths["/api/v1/auth/login"] = {"post": operation("login", "Autenticación", "Iniciar sesión", "Público. Devuelve un token Bearer firmado con itsdangerous/HMAC SHA-256. La contraseña debe conservarse exactamente. Las credenciales incorrectas reciben el mismo mensaje 401.", "Token", body="Login", public=True, errors=(401,))}
    paths["/api/v1/auth/me"] = {"get": operation("me", "Autenticación", "Consultar la cuenta autenticada", "Requiere token vigente y cuenta activa.", "Usuario")}
    for route, model, tag in (("usuarios", "Usuario", "Usuarios"), ("activos", "Activo", "Activos")):
        collection = f"/api/v1/{route}"
        identifier = "usuario_id" if route == "usuarios" else "activo_id"
        list_description = "Operadores: todos los usuarios; otras cuentas: únicamente su propio registro." if route == "usuarios" else "Todas las cuentas autenticadas pueden consultar el inventario."
        paths[collection] = {
            "get": operation(f"list_{route}", tag, f"Listar {route}", list_description + " Solo se aceptan page y per_page; una página fuera del rango devuelve data vacío.", f"{model}Page", parameters=PAGINATION),
            "post": operation(f"create_{route}", tag, f"Crear {model.lower()}", "Solo operadores configurados en API_OPERATOR_IDS." + (" La cuenta se crea sin contraseña; un operador local debe asignarla mediante flask set-password." if route == "usuarios" else " El estado inicial no puede ser prestado."), model, status=201, body=f"{model}Create", errors=(403, 409)),
        }
        permissions = "Propietario u operador." if route == "usuarios" else "Consulta: cualquier cuenta autenticada; cambios: solo operadores."
        item = f"{collection}/{{{identifier}}}"
        paths[item] = {
            "get": operation(f"get_{route}", tag, f"Consultar {model.lower()}", permissions, model, parameters=path_id(identifier), errors=(403, 404) if route == "usuarios" else (404,)),
            "put": operation(f"replace_{route}", tag, f"Actualizar {model.lower()} con campos obligatorios", permissions + " Requiere los campos obligatorios de creación; los opcionales omitidos conservan su valor.", model, body=f"{model}Replace", parameters=path_id(identifier), errors=(403, 404, 409)),
            "patch": operation(f"patch_{route}", tag, f"Actualizar parcialmente {model.lower()}", permissions + " Debe incluir al menos un campo editable.", model, body=f"{model}Patch", parameters=path_id(identifier), errors=(403, 404, 409)),
            "delete": operation(f"delete_{route}", tag, f"Dar de baja {model.lower()}", permissions + (" Desactiva el usuario; se rechaza si mantiene préstamos pendientes." if route == "usuarios" else " Cambia estado a baja; se rechaza si está prestado."), None, status=204, parameters=path_id(identifier), errors=(403, 404, 409)),
        }
    paths["/api/v1/prestamos"] = {
        "get": operation("list_prestamos", "Préstamos", "Consultar historial de préstamos", "Operadores: historial completo; otras cuentas: sus propios préstamos. Solo se aceptan page y per_page.", "PrestamoPage", parameters=PAGINATION),
        "post": operation("create_prestamo", "Préstamos", "Crear préstamo y reservar activo", "Propietario del usuario indicado u operador. Exige usuario activo, activo disponible y devolución prevista futura. La reserva impide préstamos simultáneos del mismo activo.", "Prestamo", status=201, body="PrestamoCreate", errors=(403, 404, 409)),
    }
    paths["/api/v1/prestamos/{prestamo_id}"] = {"get": operation("get_prestamo", "Préstamos", "Consultar préstamo", "Propietario del préstamo u operador.", "Prestamo", parameters=path_id("prestamo_id"), errors=(403, 404))}
    paths["/api/v1/prestamos/{prestamo_id}/devolucion"] = {"post": operation("return_prestamo", "Préstamos", "Registrar devolución y liberar activo", "Propietario del préstamo u operador. Debe enviarse exactamente {} como cuerpo JSON. La fecha efectiva se asigna en el servidor; el activo vuelve a disponible. Repetir la devolución genera 409.", "Prestamo", body="Devolucion", parameters=path_id("prestamo_id"), errors=(403, 404, 409))}
    return {
        "openapi": "3.0.3",
        "info": {"title": "StashEdu API", "version": "1.0.0", "description":
                 "Gestión de préstamos de activos tecnológicos. Registro, login, health y documentación son públicos; el resto requiere Authorization: Bearer <token>. "
                 "El token firmado itsdangerous expira según AUTH_TOKEN_MAX_AGE (3600 segundos por defecto), se revoca al cambiar la contraseña y se rechaza para usuarios inactivos. "
                 "API_OPERATOR_IDS concede permisos administrativos a IDs de cuentas existentes mediante configuración local. Las demás cuentas solo acceden a sus usuarios/préstamos y consultan activos. "
                 "Esta política provisional no implementa JWT ni un sistema configurable de roles. Los cuerpos son objetos JSON de máximo 64 KiB; los campos desconocidos y las consultas no declaradas se rechazan. "
                 "Fechas de préstamo se devuelven en UTC con sufijo Z; created_at/updated_at representan UTC sin sufijo de zona. PUT exige los campos obligatorios y conserva los opcionales omitidos."},
        "servers": [{"url": "/", "description": "Mismo servidor que publica esta documentación"}],
        "tags": [{"name": name} for name in ("Sistema", "Autenticación", "Usuarios", "Activos", "Préstamos")],
        "security": [{"BearerAuth": []}],
        "paths": paths,
        "components": {"securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer",
                         "description": "Token firmado itsdangerous/HMAC SHA-256 obtenido mediante login; no JWT."}},
                       "schemas": schemas()},
    }


@docs_bp.get("/openapi.json")
def openapi():
    return jsonify(build_spec())

# StashEdu

API REST en Flask y MySQL para gestionar usuarios, activos tecnológicos, préstamos y devoluciones.

## Instalación y arranque

Desde este directorio, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Solo si todavía no tienes .env:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Configura las credenciales MySQL de `.env`, copia la clave aleatoria generada a `SECRET_KEY`
y conserva `FLASK_DEBUG=0`. `AUTH_TOKEN_MAX_AGE` indica la duración del token en segundos
(3600 por defecto). Nunca subas `.env` al repositorio.

La base debe existir: `sql/01_configuracion.sql` ofrece una configuración inicial.
La ruta recomendada para crear **o actualizar** las tablas es Alembic:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe run.py
```

Si las tablas ya se crearon con `sql/02_tablas_fase1.sql`, ese script también registra
la revisión inicial; ejecuta únicamente `db upgrade` para añadir préstamos y hashes.
No vuelvas a ejecutar el script inicial sobre una base poblada.

Los nuevos usuarios se registran por HTTP. Para usuarios históricos sin contraseña:

```powershell
.\.venv\Scripts\python.exe -m flask --app run set-password 1
```

El comando solicita la contraseña y confirmación sin mostrarlas. No existe contraseña
predeterminada. Para administrar activos y cuentas, identifica primero una cuenta
existente y de confianza y añade su ID a `API_OPERATOR_IDS` en `.env`, por ejemplo `1,2`.
Reinicia el servidor después de modificar la configuración. No reserves IDs que todavía
no existen: podrían ser ocupados por registros públicos futuros.

## Contrato HTTP

Base local: `http://127.0.0.1:5000`. Swagger UI está en `/docs/` y la especificación
OpenAPI 3.0.3 en `/openapi.json`. La interfaz y sus recursos se sirven localmente;
no dependen de una CDN. Puedes importar la especificación en Postman.

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/v1/health` | Estado de conexión a MySQL, público |
| POST | `/api/v1/auth/register` | Registro público, responde 201 |
| POST | `/api/v1/auth/login` | Login público, devuelve token Bearer |
| GET | `/api/v1/auth/me` | Perfil autenticado |
| GET, POST | `/api/v1/usuarios` | Listar cuentas propias / crear cuenta mediante operador |
| GET, PUT, PATCH, DELETE | `/api/v1/usuarios/{id}` | Propietario u operador; DELETE es baja lógica |
| GET, POST | `/api/v1/activos` | Lectura autenticada; creación mediante operador |
| GET, PUT, PATCH, DELETE | `/api/v1/activos/{id}` | Lectura autenticada; escrituras mediante operador |
| GET, POST | `/api/v1/prestamos` | Historial propio o completo para operadores / crear préstamo |
| GET | `/api/v1/prestamos/{id}` | Consultar préstamo propio o mediante operador |
| POST | `/api/v1/prestamos/{id}/devolucion` | Registrar devolución propia o mediante operador |

Registro de ejemplo:

```json
{
  "nombre_completo": "Ana Pérez",
  "documento": "1061000001",
  "email": "ana@example.com",
  "tipo_usuario": "estudiante",
  "password": "Una frase secreta larga"
}
```

En `/api/v1/auth/login`, envía `email` y `password`. Copia `access_token` y envía
`Authorization: Bearer <token>` en las rutas protegidas. En Swagger, usa **Authorize**
con el token, sin escribir el prefijo Bearer. Las contraseñas se conservan exactamente,
incluidos los espacios; se guarda únicamente un hash scrypt con salt aleatorio.
Un cambio de contraseña invalida los tokens anteriores. Las cuentas inactivas no
pueden iniciar sesión ni utilizar tokens ya emitidos.

Crear préstamo (usa IDs existentes y una fecha futura):

```json
{
  "usuario_id": 1,
  "activo_id": 1,
  "fecha_devolucion_prevista": "2026-12-01T17:00:00-05:00",
  "observaciones": "Préstamo para clase"
}
```

Para devolverlo, envía `{}` a `/api/v1/prestamos/{id}/devolucion`. Responde 200;
repetir una devolución responde 409. La fecha real la fija el servidor en UTC.

## Datos, reglas y validación

- El activo pasa de `disponible` a `prestado` y vuelve a `disponible` al devolverlo.
  Un `UPDATE` condicional y la transacción evitan dobles préstamos del mismo activo.
- Usuario inactivo o activo en mantenimiento/baja/prestado: 409. Referencia inexistente: 404.
- No se puede editar el estado ni dar de baja un activo prestado, ni desactivar un usuario
  con préstamos pendientes. Los metadatos del activo siguen siendo editables por operadores.
- Las bajas son lógicas y conservan el historial. Las claves foráneas impiden borrar
  físicamente usuarios o activos referenciados.
- Fechas de préstamo: ISO 8601 con zona horaria; se normalizan a UTC y salen con `Z`.
  `retrasado` compara el plazo con la devolución real o con la hora actual.
- Las escrituras exigen objetos JSON y rechazan campos desconocidos. POST/PUT exigen
  campos obligatorios; PATCH exige al menos un campo editable.
- Se validan tipos estrictos (un booleano no es un ID), longitudes, enums, email,
  fechas reales y contraseñas de 12 a 128 caracteres. Los emails se normalizan a minúsculas.
- Límite de cuerpo: 64 KiB. Descripción: 10000 caracteres y límite UTF-8 de MySQL TEXT.
  La paginación admite `page >= 1` y `1 <= per_page <= 100`; valores inválidos se rechazan.
- Listados: `{"data": [], "meta": {"page": 1, "per_page": 10, "total": 0, "pages": 0}}`.
  Los filtros avanzados de préstamos no forman parte de esta entrega.

Los errores usan `{"error": "mensaje", "detalles": {...}}` (detalles opcionales).
400: validación; 401: autenticación; 403: permisos; 404: recurso inexistente;
409: conflicto; 413: cuerpo demasiado grande; 415: contenido no JSON;
500: fallo interno; 503: MySQL o configuración de autenticación no disponibles.
Las respuestas no exponen contraseñas, hashes ni información interna de SQL.

## Pruebas y alcance

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -v
```

Las pruebas habituales usan SQLite en memoria, sin acceder a la base del proyecto.
Para integración MySQL, usando las credenciales locales y permisos CREATE/DROP DATABASE:

```powershell
$env:RUN_MYSQL_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest tests.test_mysql_integration -v
Remove-Item Env:RUN_MYSQL_TESTS
```

Esta suite crea y elimina únicamente una base aleatoria `stashedu_test_<uuid>`;
valida migraciones con usuarios históricos, rollback y carreras de préstamo/devolución/baja.
No ejecuta migraciones sobre `DB_NAME`.

Los seis puntos asignados son Create Loan, Record Return, Registration, Password Hashing,
Swagger y Data validation. Las ramas están encadenadas: `feature/create-loan` →
`feature/record-return` → `feature/password-hashing` → `feature/registration` →
`feature/swagger` → `feature/data-validation`. La última reúne todos los cambios;
no se ha fusionado automáticamente en `main`.

Quedan para el proyecto completo JWT, roles/permisos persistidos, filtros y consultas
avanzadas y una colección Postman ejecutada. El token actual es firmado y expirable
mediante ItsDangerous; no es JWT. La autorización mínima propietario/operador procede
de configuración local y no sustituye ese sistema de roles. Los informes de validación
y la correlación con el documento de referencia están en la nota Obsidian
`estado_proyecto_y_desarrollo.md` del proyecto StashEdu.

Referencias técnicas: [Werkzeug](https://werkzeug.palletsprojects.com/en/stable/utils/#werkzeug.security.generate_password_hash),
[ItsDangerous](https://itsdangerous.palletsprojects.com/en/stable/timed/),
[OpenAPI Bearer](https://swagger.io/docs/specification/v3_0/authentication/bearer-authentication/).

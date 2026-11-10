# StashEdu

API REST para gestionar el préstamo de activos tecnológicos (portátiles, proyectores,
tablets, cámaras…) de una institución educativa a estudiantes, docentes y funcionarios.

> **Estado actual: Fase 3 — Seguridad.** Sobre la Fase 1 (Flask, conexión a MySQL/MariaDB,
> modelos y CRUD de usuarios y activos) y la Fase 2 (préstamos, devoluciones, reglas de
> negocio, consultas y filtros) se agregan registro/login, hash de contraseñas, JWT y
> permisos por rol (`admin`, `operador`, `consulta`).

## Requisitos

- Python 3.11 o superior.
- MySQL 8.0.16+ o MariaDB 10.2.1+
- curl o Postman para probar la API.

## Instalación

### 1. Clonar el repositorio e instalar las dependencias

```bash
git clone <url-del-repositorio>
cd StashEdu
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Crear la base de datos y un usuario para la aplicación

Con una cuenta administradora de MySQL/MariaDB, crea la base de datos vacía:

```bash
mariadb -u root -p < sql/01_configuracion.sql     # o: sudo mariadb < sql/01_configuracion.sql
```

Luego crea un usuario propio para la aplicación, con permisos solo sobre esa base
(la aplicación no debe conectarse como `root`):

```sql
CREATE USER 'stashedu'@'localhost' IDENTIFIED BY 'tu_contraseña';
GRANT ALL PRIVILEGES ON prestamos_activos.* TO 'stashedu'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configurar las variables de entorno

```bash
cp .env.example .env               # Windows: copy .env.example .env
```

Edita `.env` con tus datos:

| Variable | Ejemplo | Descripción |
|---|---|---|
| `DB_HOST` | `localhost` | Servidor de base de datos |
| `DB_PORT` | `3306` | Puerto |
| `DB_USER` | `stashedu` | Usuario creado en el paso 2 |
| `DB_PASSWORD` | `tu_contraseña` | Si tiene espacios o `#`, escríbela entre comillas: `"mi #clave"` |
| `DB_NAME` | `prestamos_activos` | Nombre de la base de datos |
| `FLASK_DEBUG` | `1` | `1` recarga el servidor al guardar cambios (solo en desarrollo) |
| `SECRET_KEY` | *(64 caracteres hex)* | Firma de los JWT, mínimo 32 caracteres. Genérala con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `AUTH_TOKEN_MAX_AGE` | `3600` | Segundos que dura un token |

El archivo `.env` contiene credenciales y **no se sube al repositorio**.

### 4. Crear las tablas con las migraciones

```bash
flask --app run db upgrade
```

Crea las tablas `tipos_usuario`, `roles`, `usuarios`, `activos` y `prestamos`, e inserta los
tipos de usuario con sus límites de préstamo y los roles (ver [Fase 3](#probar-la-fase-3)):

| id | Tipo | Máximo de préstamos sin devolver | Máximo de días por préstamo |
|---|---|---|---|
| 1 | `estudiante` | 1 | 3 |
| 2 | `docente` | 3 | 15 |
| 3 | `funcionario` | 2 | 7 |

Si tu base ya tenía una fase anterior, el mismo comando solo agrega lo que falta.

### 5. Crear el primer administrador

Todas las rutas (salvo `/health` y `/auth/login`) exigen un token, y las cuentas las crea un
`admin`. El primero se crea desde la terminal:

```bash
flask --app run crear-admin
```

Pide nombre, documento, email y contraseña (12 a 128 caracteres). Con
`flask --app run set-password <usuario_id>` se cambia la contraseña de una cuenta existente.

### 6. Ejecutar la API

```bash
python run.py
```

La API queda disponible en `http://127.0.0.1:5000/api/v1`.

## Probar la Fase 1

### Comprobación rápida

> Desde la Fase 3, cada petición lleva el header `Authorization: Bearer <token>` (ver
> [Fase 3](#probar-la-fase-3)). En los ejemplos con curl, guarda antes el token en `$TOKEN`.

```bash
curl http://127.0.0.1:5000/api/v1/health
```

Debe responder `200` con `{"status": "ok", "database": "connected"}`. Si responde `503`,
la API está encendida pero no llega a la base de datos (revisa el paso 3).

### Endpoints

Todas las rutas comienzan con `/api/v1`.

| Método | Ruta | Descripción | Éxito |
|---|---|---|---|
| GET | `/health` | Estado de la API y de la conexión a la base de datos | 200 |
| GET | `/tipos-usuario` | Catálogo de tipos de usuario | 200 |
| GET | `/usuarios` | Listar usuarios. Filtros: `?tipo_usuario_id=1&habilitado=true` | 200 |
| GET | `/usuarios/{id}` | Ver un usuario | 200 |
| POST | `/usuarios` | Crear un usuario | 201 |
| PUT | `/usuarios/{id}` | Actualizar un usuario (exige los campos obligatorios) | 200 |
| PATCH | `/usuarios/{id}` | Actualizar solo algunos campos | 200 |
| DELETE | `/usuarios/{id}` | Deshabilitar un usuario (baja lógica; 409 si tiene préstamos sin devolver) | 204 |
| GET | `/activos` | Listar activos. Filtros: `?estado=disponible&categoria=portatil` | 200 |
| GET | `/activos/{id}` | Ver un activo | 200 |
| POST | `/activos` | Crear un activo | 201 |
| PUT | `/activos/{id}` | Actualizar un activo (exige los campos obligatorios) | 200 |
| PATCH | `/activos/{id}` | Actualizar solo algunos campos | 200 |
| DELETE | `/activos/{id}` | Dar de baja un activo (pasa a estado `baja`; 409 si está prestado) | 204 |

Los listados admiten paginación con `?page=1&per_page=10` (máximo 100 por página).

**Campos de un usuario:** `nombre_completo`\*, `documento`\*, `email`\*, `tipo_usuario_id`\*,
`telefono`, `habilitado`.

**Campos de un activo:** `codigo_inventario`\*, `nombre`\*, `categoria`\*, `marca`, `modelo`,
`numero_serie`, `estado`.

- `categoria`: `portatil`, `proyector`, `tablet`, `camara` u `otro`.
- `estado`: `disponible` (por defecto), `mantenimiento` o `baja`. El estado `prestado` lo
  asignan los préstamos y no se puede poner a mano; un activo prestado solo vuelve a
  `disponible` con su devolución.

(\*) obligatorio.

### Ejemplos con curl

```bash
# Crear un usuario (tipo 2 = docente)
curl -X POST http://127.0.0.1:5000/api/v1/usuarios \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nombre_completo": "Ana Pérez", "documento": "1001", "email": "ana@uni.edu.co", "tipo_usuario_id": 2}'

# Crear un activo
curl -X POST http://127.0.0.1:5000/api/v1/activos \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"codigo_inventario": "INV-001", "nombre": "Portátil Lenovo T14", "categoria": "portatil", "numero_serie": "SN-A1"}'

# Listar los portátiles disponibles
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/v1/activos?estado=disponible&categoria=portatil"

# Pasar el activo 1 a mantenimiento
curl -X PATCH http://127.0.0.1:5000/api/v1/activos/1 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"estado": "mantenimiento"}'

# Deshabilitar el usuario 1
curl -X DELETE http://127.0.0.1:5000/api/v1/usuarios/1 -H "Authorization: Bearer $TOKEN"
```

### Con Postman

1. Crea una variable `base_url` con el valor `http://127.0.0.1:5000/api/v1`.
2. Usa URLs como `{{base_url}}/usuarios`.
3. En `POST`, `PUT` y `PATCH`, elige **Body → raw → JSON**; Postman añade el encabezado
   `Content-Type: application/json`.
4. En la pestaña **Authorization** elige **Bearer Token** y pega el token del login.

### Casos de error para probar

| Caso | Petición | Respuesta esperada |
|---|---|---|
| Faltan campos obligatorios | `POST /usuarios` con `{"nombre_completo": "Ana"}` | 400 y la lista de campos faltantes |
| Cuerpo que no es JSON | `POST /usuarios` con texto plano | 400 |
| Correo inválido | `"email": "ana-sin-arroba"` | 400 |
| Tipo de usuario inexistente | `"tipo_usuario_id": 99` | 400 |
| Documento o correo repetido | Crear dos veces el mismo usuario | 409 |
| Correo repetido con otras mayúsculas | `ANA@UNI.EDU.CO` si ya existe `ana@uni.edu.co` | 409 |
| Categoría inválida | `"categoria": "nevera"` | 400 y los valores permitidos |
| Estado reservado | `PATCH /activos/1` con `{"estado": "prestado"}` | 400 |
| Código de inventario repetido | Crear dos veces el mismo activo | 409 |
| Filtro inválido | `GET /activos?estado=roto` | 400 |
| Recurso inexistente | `GET /usuarios/9999` | 404 |
| Método no permitido | `POST /activos/1` | 405 |
| Base de datos apagada | Cualquier petición con MySQL/MariaDB detenido | 503 |

### Formato de las respuestas

- Un recurso se devuelve como objeto JSON. Las fechas están en UTC (terminan en `Z`).
- Los listados devuelven `{"data": [...], "meta": {"page", "per_page", "total", "pages"}}`.
- Los errores siempre tienen la forma `{"error": "mensaje"}`, a veces con `"detalles"`.

## Probar la Fase 2

### Endpoints de préstamos

| Método | Ruta | Descripción | Éxito |
|---|---|---|---|
| POST | `/prestamos` | Crear un préstamo | 201 |
| POST | `/prestamos/{id}/devolucion` | Registrar la devolución | 200 |
| GET | `/prestamos` | Listar préstamos. Filtros: `?estado=&usuario_id=&activo_id=&desde=&hasta=` | 200 |
| GET | `/prestamos/{id}` | Ver un préstamo | 200 |
| GET | `/usuarios/{id}/prestamos` | Historial de un usuario. Filtros: `?estado=&desde=&hasta=` | 200 |
| GET | `/activos/{id}/prestamos` | Historial de un activo. Filtros: `?estado=&desde=&hasta=` | 200 |

**Crear un préstamo:** `usuario_id`\*, `activo_id`\*, `dias`, `observaciones_entrega`.
Si no se envía `dias`, se usa el máximo del tipo de usuario. La fecha del préstamo y la de
vencimiento las calcula el servidor.

**Registrar la devolución:** cuerpo opcional con `observaciones_devolucion`. La fecha de
devolución la pone el servidor.

### Reglas de negocio

- Solo se presta un activo en estado `disponible`; al prestarlo pasa a `prestado` y al
  devolverlo vuelve a `disponible`, en la misma transacción que guarda el préstamo.
- Un usuario deshabilitado no puede pedir prestado.
- Cada tipo de usuario tiene un máximo de préstamos sin devolver y un máximo de días por
  préstamo (ver la tabla del paso 4).
- Un préstamo se devuelve una sola vez.
- No se puede dar de baja ni cambiar el estado de un activo prestado, ni deshabilitar a un
  usuario con préstamos sin devolver.
- Si dos peticiones intentan prestar el mismo activo al mismo tiempo, solo una lo consigue.

### Estado de un préstamo

El estado no se guarda en la base de datos: se calcula a partir de las fechas.

| Estado | Condición |
|---|---|
| `activo` | Sin devolver y la fecha de vencimiento no ha pasado |
| `vencido` | Sin devolver y la fecha de vencimiento ya pasó |
| `devuelto` | Devuelto antes o en la fecha de vencimiento |
| `devuelto_con_retraso` | Devuelto después de la fecha de vencimiento |

`dias_retraso` indica cuántos días (o fracción de día) pasaron después del vencimiento;
es `0` si el préstamo va o fue devuelto a tiempo.

### Filtros de consulta

- `estado`: uno de los cuatro estados anteriores, o `pendiente` para ver todos los préstamos
  sin devolver (`activo` + `vencido`).
- `usuario_id`, `activo_id`: solo en `GET /prestamos`.
- `desde`, `hasta`: fechas `AAAA-MM-DD` (UTC) sobre la fecha del préstamo; `hasta` incluye
  todo ese día.
- Los resultados van del préstamo más reciente al más antiguo y admiten `?page=&per_page=`.

### Ejemplos con curl

```bash
# Prestar el activo 1 al usuario 1 durante 2 días
curl -X POST http://127.0.0.1:5000/api/v1/prestamos \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"usuario_id": 1, "activo_id": 1, "dias": 2, "observaciones_entrega": "Con cargador"}'

# Registrar la devolución del préstamo 1
curl -X POST http://127.0.0.1:5000/api/v1/prestamos/1/devolucion \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"observaciones_devolucion": "Sin daños"}'

# Préstamos vencidos (quién tiene un activo y no lo ha devuelto a tiempo)
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/v1/prestamos?estado=vencido"

# Quién tiene ahora el activo 1 (préstamo sin devolver, esté vencido o no)
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/v1/activos/1/prestamos?estado=pendiente"

# Historial del activo 1 en octubre
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/v1/activos/1/prestamos?desde=2026-10-01&hasta=2026-10-31"
```

### Colección de Postman

[`docs/postman/StashEdu_fase2.postman_collection.json`](docs/postman/StashEdu_fase2.postman_collection.json)
recorre el flujo completo: crea sus propios usuarios y activos, presta, prueba los casos de
error, consulta con filtros y registra la devolución. Impórtala en Postman (**Import**) y
ejecútala en orden con **Run collection**; cada petición comprueba el código de respuesta.
La variable `base_url` apunta a `http://127.0.0.1:5000/api/v1`. Desde la Fase 3 la primera
petición inicia sesión: escribe el correo y la contraseña de un admin en las variables
`admin_email` y `admin_password`.

### Casos de error para probar

| Caso | Petición | Respuesta esperada |
|---|---|---|
| Faltan campos | `POST /prestamos` con `{"usuario_id": 1}` | 400 |
| Identificador inválido | `"usuario_id": "uno"` o `"dias": 0` | 400 |
| Más días de los permitidos | Estudiante con `"dias": 4` | 400 |
| Usuario o activo inexistente | `"usuario_id": 9999` | 404 |
| Activo no disponible | Prestar un activo `prestado`, en `mantenimiento` o de `baja` | 409 |
| Usuario deshabilitado | Prestar a un usuario con `habilitado = false` | 409 |
| Máximo de préstamos | Un estudiante con un préstamo sin devolver pide otro | 409 |
| Devolución repetida | `POST /prestamos/1/devolucion` dos veces | 409 |
| Préstamo inexistente | `GET /prestamos/9999` | 404 |
| Baja de un activo prestado | `DELETE /activos/{id}` | 409 |
| Deshabilitar usuario con préstamos | `DELETE /usuarios/{id}` | 409 |
| Filtro inválido | `GET /prestamos?estado=perdido` o `?desde=ayer` | 400 |

### Pruebas automatizadas

```bash
python -m unittest discover -v
```

Usan SQLite en memoria, así que no tocan la base de datos MySQL/MariaDB.

## Probar la Fase 3

### Endpoints de autenticación

| Método | Ruta | Quién | Body | Éxito | Errores |
|---|---|---|---|---|---|
| POST | `/auth/login` | Público | `email`\*, `password`\* | 200 + token JWT | 400 · 401 credenciales inválidas |
| POST | `/auth/register` | `admin` | `usuario_id`\*, `password`\*, `rol_id`\* | 201 + usuario | 400 · 401 · 403 · 404 usuario · 409 ya tiene cuenta o está deshabilitado |
| GET | `/auth/me` | Cualquier cuenta | — | 200 + usuario | 401 |
| GET | `/roles` | Cualquier cuenta | — | 200 + roles | 401 |

- **Cuentas.** Un usuario que solo pide prestado no tiene cuenta (`rol_id` y `password_hash`
  en `NULL`). `POST /auth/register` le da un rol y una contraseña a un usuario que **ya
  existe**. Solo lo hace un `admin`; no hay autoregistro público.
- **Contraseñas.** Se guardan con hash scrypt y salt aleatorio, nunca en texto plano. Deben
  tener de 12 a 128 caracteres. La respuesta nunca incluye `password_hash`.
- **Login.** Responde siempre `Credenciales inválidas.`, sin decir si el correo existe.

Respuesta del login:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "usuario": {"id": 3, "nombre_completo": "Admin Demo", "rol": "admin", "...": "..."}
}
```

### El token (JWT)

Es un JWT firmado con HS256 y `SECRET_KEY`. Se envía en cada petición con el header
`Authorization: Bearer <token>`. Contiene:

| Claim | Significado |
|---|---|
| `sub` | id del usuario |
| `rol` | rol al iniciar sesión (informativo; los permisos se leen de la base de datos) |
| `iat` / `exp` | emisión y vencimiento (`AUTH_TOKEN_MAX_AGE` segundos) |
| `ver` | huella de la contraseña: si cambia, los tokens anteriores dejan de valer |

Un token deja de servir si expira, si se altera la firma, si la cuenta se deshabilita o si
cambia la contraseña.

### Roles y permisos

| Rol | Puede |
|---|---|
| `admin` | Todo, incluido `DELETE` y registrar cuentas |
| `operador` | Ver todo; crear/editar usuarios y activos; crear préstamos y registrar devoluciones |
| `consulta` | Solo `GET` |

Sin token: **401**. Con token pero sin permiso: **403**. `/health` y `/auth/login` son
públicos. Un `operador` no puede editar la cuenta de otro operador ni de un admin.

Cada préstamo guarda quién lo entregó (`entregado_por`) y quién recibió la devolución
(`recibido_por`), tomados del token:

```json
"entregado_por": {"id": 4, "nombre_completo": "Operador Demo"},
"recibido_por": null
```

### Ejemplos con curl

```bash
# Iniciar sesión y guardar el token
TOKEN=$(curl -s -X POST http://127.0.0.1:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@uni.edu.co", "password": "tu contraseña"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Mi perfil
curl http://127.0.0.1:5000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"

# Dar cuenta de operador (rol 2) al usuario 1
curl -X POST http://127.0.0.1:5000/api/v1/auth/register \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"usuario_id": 1, "password": "Clave segura 123", "rol_id": 2}'
```

### Colección de Postman

[`docs/postman/StashEdu_fase3.postman_collection.json`](docs/postman/StashEdu_fase3.postman_collection.json)
prueba el login, el registro de cuentas y los permisos de cada rol. Antes de ejecutarla, crea el
primer admin (paso 5) y escribe su correo y contraseña en las variables `admin_email` y
`admin_password`. La colección crea sus propias personas, cuentas, activos y préstamos.

### Casos de error para probar

| Caso | Petición | Respuesta esperada |
|---|---|---|
| Sin token | `GET /usuarios` sin `Authorization` | 401 |
| Token alterado o de otra clave | `Authorization: Bearer abc.def.ghi` | 401 |
| Token expirado | Esperar `AUTH_TOKEN_MAX_AGE` segundos | 401 |
| Cuenta deshabilitada o contraseña cambiada | Usar un token emitido antes | 401 |
| Contraseña incorrecta o correo inexistente | `POST /auth/login` | 401 `Credenciales inválidas.` |
| Faltan campos | `POST /auth/login` con solo `email` | 400 |
| Rol `consulta` modifica algo | `POST /activos` | 403 |
| Rol `operador` borra algo | `DELETE /activos/{id}` | 403 |
| Rol no admin registra cuentas | `POST /auth/register` | 403 |
| Usuario inexistente | `POST /auth/register` con `usuario_id: 9999` | 404 |
| Rol inexistente o contraseña corta | `rol_id: 99` o `password: "corta"` | 400 |
| Cuenta repetida | Registrar dos veces el mismo usuario | 409 |
| Falta `SECRET_KEY` en `.env` | Cualquier ruta protegida | 503 |

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `/health` responde 503 | El servidor de base de datos está apagado o los datos de `.env` son incorrectos |
| `Access denied for user` | Usuario, contraseña o host incorrectos en `.env` |
| `Unknown database 'prestamos_activos'` | Falta el paso 2 |
| `Table ... doesn't exist` | Falta `flask --app run db upgrade` (paso 4) |
| Todo responde 401 | Falta el header `Authorization: Bearer <token>` o el token expiró: vuelve a iniciar sesión |
| Toda ruta protegida responde 503 | Falta `SECRET_KEY` (32+ caracteres) en `.env` |
| `Can't locate revision ...` | La base fue creada con migraciones antiguas: bórrala (`DROP DATABASE prestamos_activos;`) y repite los pasos 2 y 4 |

## Documentación

- [`docs/diagrama_er.png`](docs/diagrama_er.png): modelo entidad-relación.
- [`docs/esquema_bd.sql`](docs/esquema_bd.sql): diseño completo de la base de datos
  (referencia; las tablas se crean con las migraciones).

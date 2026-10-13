# StashEdu

API REST para gestionar el préstamo de activos tecnológicos (portátiles, proyectores,
tablets, cámaras…) de una institución educativa a estudiantes, docentes y funcionarios.

> **Estado actual: Fase 1 — API básica.** Incluye la configuración de Flask, la conexión a
> MySQL/MariaDB, los modelos y el CRUD de usuarios y de activos.

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

El archivo `.env` contiene credenciales y **no se sube al repositorio**.

### 4. Crear las tablas con las migraciones

```bash
flask --app run db upgrade
```

Crea las tablas `tipos_usuario`, `usuarios` y `activos`, e inserta los tipos de usuario:
`1 = estudiante`, `2 = docente` y `3 = funcionario`.

### 5. Ejecutar la API

```bash
python run.py
```

La API queda disponible en `http://127.0.0.1:5000/api/v1`.

## Probar la Fase 1

### Comprobación rápida

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
| DELETE | `/usuarios/{id}` | Deshabilitar un usuario (baja lógica) | 204 |
| GET | `/activos` | Listar activos. Filtros: `?estado=disponible&categoria=portatil` | 200 |
| GET | `/activos/{id}` | Ver un activo | 200 |
| POST | `/activos` | Crear un activo | 201 |
| PUT | `/activos/{id}` | Actualizar un activo (exige los campos obligatorios) | 200 |
| PATCH | `/activos/{id}` | Actualizar solo algunos campos | 200 |
| DELETE | `/activos/{id}` | Dar de baja un activo (pasa a estado `baja`) | 204 |

Los listados admiten paginación con `?page=1&per_page=10` (máximo 100 por página).

**Campos de un usuario:** `nombre_completo`\*, `documento`\*, `email`\*, `tipo_usuario_id`\*,
`telefono`, `habilitado`.

**Campos de un activo:** `codigo_inventario`\*, `nombre`\*, `categoria`\*, `marca`, `modelo`,
`numero_serie`, `estado`.

- `categoria`: `portatil`, `proyector`, `tablet`, `camara` u `otro`.
- `estado`: `disponible` (por defecto), `mantenimiento` o `baja`. El estado `prestado` lo
  asignarán los préstamos (Fase 2) y no se puede poner a mano.

(\*) obligatorio.

### Ejemplos con curl

```bash
# Crear un usuario (tipo 2 = docente)
curl -X POST http://127.0.0.1:5000/api/v1/usuarios \
  -H "Content-Type: application/json" \
  -d '{"nombre_completo": "Ana Pérez", "documento": "1001", "email": "ana@uni.edu.co", "tipo_usuario_id": 2}'

# Crear un activo
curl -X POST http://127.0.0.1:5000/api/v1/activos \
  -H "Content-Type: application/json" \
  -d '{"codigo_inventario": "INV-001", "nombre": "Portátil Lenovo T14", "categoria": "portatil", "numero_serie": "SN-A1"}'

# Listar los portátiles disponibles
curl "http://127.0.0.1:5000/api/v1/activos?estado=disponible&categoria=portatil"

# Pasar el activo 1 a mantenimiento
curl -X PATCH http://127.0.0.1:5000/api/v1/activos/1 \
  -H "Content-Type: application/json" \
  -d '{"estado": "mantenimiento"}'

# Deshabilitar el usuario 1
curl -X DELETE http://127.0.0.1:5000/api/v1/usuarios/1
```

### Con Postman

1. Crea una variable `base_url` con el valor `http://127.0.0.1:5000/api/v1`.
2. Usa URLs como `{{base_url}}/usuarios`.
3. En `POST`, `PUT` y `PATCH`, elige **Body → raw → JSON**; Postman añade el encabezado
   `Content-Type: application/json`.

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

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `/health` responde 503 | El servidor de base de datos está apagado o los datos de `.env` son incorrectos |
| `Access denied for user` | Usuario, contraseña o host incorrectos en `.env` |
| `Unknown database 'prestamos_activos'` | Falta el paso 2 |
| `Table ... doesn't exist` | Falta `flask --app run db upgrade` (paso 4) |
| `Can't locate revision ...` | La base fue creada con migraciones antiguas: bórrala (`DROP DATABASE prestamos_activos;`) y repite los pasos 2 y 4 |

## Documentación

- [`docs/diagrama_er.png`](docs/diagrama_er.png): modelo entidad-relación.
- [`docs/esquema_bd.sql`](docs/esquema_bd.sql): diseño completo de la base de datos
  (referencia; las tablas se crean con las migraciones).

-- =====================================================================
-- DOCUMENTO DE DISEÑO: NO EJECUTAR SOBRE LA BASE DE LA APLICACIÓN.
-- Las tablas se crean con las migraciones (`flask --app run db upgrade`);
-- cada fase implementa la parte que le toca de este diseño con su migración.
-- Diagrama: docs/diagrama_er.png
-- =====================================================================
-- StashEdu · Esquema completo (Fases 1 a 4)
-- Requiere MySQL 8.0.16+ o MariaDB 10.2.1+ (antes, los CHECK se ignoran).
-- FECHAS: todas son UTC y las escribe SIEMPRE la API (nunca la base de datos,
-- por eso no hay DEFAULT CURRENT_TIMESTAMP ni ON UPDATE). "Ahora" también lo
-- calcula la API en UTC. Así la zona horaria del servidor no influye.
-- DATETIME(6): con microsegundos, para que MySQL no redondee al segundo.
-- Índices: solo los de PRIMARY KEY, UNIQUE y los que MySQL crea solo para
-- cada FOREIGN KEY. Se añaden más (CREATE INDEX) cuando una consulta lenta
-- lo justifique, no antes.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS prestamos_activos
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE prestamos_activos;

-- ---------------------------------------------------------------------
-- Catálogos
-- tipos_usuario: para quien PIDE prestado. Los límites dependen del tipo.
-- roles:         para quien OPERA el sistema (permisos de la API, Fase 3).
--                Qué puede hacer cada rol se define en el código.
-- ---------------------------------------------------------------------
CREATE TABLE tipos_usuario (
    id                    TINYINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    codigo                VARCHAR(20)       NOT NULL,
    descripcion           VARCHAR(100)      NOT NULL,
    max_prestamos_activos TINYINT UNSIGNED  NOT NULL,
    dias_max_prestamo     SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tipos_usuario_codigo (codigo),
    CONSTRAINT chk_tipos_usuario_limites
        CHECK (max_prestamos_activos > 0 AND dias_max_prestamo > 0)
) ENGINE=InnoDB;

CREATE TABLE roles (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo      VARCHAR(20)      NOT NULL,
    descripcion VARCHAR(100)     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_roles_codigo (codigo)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- usuarios: toda persona registrada.
--   - Quien solo pide prestado: rol_id y password_hash son NULL.
--   - Quien opera el sistema:   tiene rol_id y password_hash (login/JWT).
-- El CHECK obliga a que ambos existan juntos o ninguno.
-- IMPORTANTE: el serializador de Usuario NUNCA debe incluir password_hash.
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
    id              INT              NOT NULL AUTO_INCREMENT,
    nombre_completo VARCHAR(120)      NOT NULL,
    documento       VARCHAR(20)       NOT NULL,
    email           VARCHAR(120)      NOT NULL,
    telefono        VARCHAR(20),
    tipo_usuario_id TINYINT UNSIGNED  NOT NULL,
    rol_id          TINYINT UNSIGNED,
    password_hash   VARCHAR(255),              -- solo el hash (bcrypt/scrypt/argon2)
    habilitado      BOOL              NOT NULL DEFAULT 1,   -- baja lógica
    created_at      DATETIME(6)       NOT NULL,   -- UTC, la pone la API
    updated_at      DATETIME(6)       NOT NULL,   -- UTC, la pone la API
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuarios_documento (documento),
    UNIQUE KEY uq_usuarios_email (email),
    CONSTRAINT fk_usuarios_tipo FOREIGN KEY (tipo_usuario_id)
        REFERENCES tipos_usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_usuarios_rol FOREIGN KEY (rol_id)
        REFERENCES roles (id) ON DELETE RESTRICT,
    CONSTRAINT chk_usuarios_cuenta
        CHECK ((password_hash IS NULL) = (rol_id IS NULL))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- activos: equipos que se prestan.
-- ---------------------------------------------------------------------
CREATE TABLE activos (
    id                INT          NOT NULL AUTO_INCREMENT,
    codigo_inventario VARCHAR(30)  NOT NULL,
    nombre            VARCHAR(100) NOT NULL,
    categoria         VARCHAR(30)  NOT NULL,
    marca             VARCHAR(60),
    modelo            VARCHAR(60),
    numero_serie      VARCHAR(60),          -- NULL permitido: UNIQUE admite varios NULL
    estado            VARCHAR(20)  NOT NULL DEFAULT 'disponible',
    created_at        DATETIME(6)  NOT NULL,   -- UTC, la pone la API
    updated_at        DATETIME(6)  NOT NULL,   -- UTC, la pone la API
    PRIMARY KEY (id),
    UNIQUE KEY uq_activos_codigo_inventario (codigo_inventario),
    UNIQUE KEY uq_activos_numero_serie (numero_serie),
    CONSTRAINT chk_activos_categoria
        CHECK (categoria IN ('portatil', 'proyector', 'tablet', 'camara', 'otro')),
    CONSTRAINT chk_activos_estado
        CHECK (estado IN ('disponible', 'prestado', 'mantenimiento', 'baja'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- prestamos: un registro por préstamo; solo se guardan hechos (fechas).
-- El estado se DERIVA, no se guarda:
--   fecha_devolucion NULL y fecha_vencimiento < ahora  -> vencido
--   fecha_devolucion NULL                              -> activo
--   fecha_devolucion > fecha_vencimiento               -> devuelto con retraso
--   en otro caso                                       -> devuelto
-- Regla "un activo no puede tener dos préstamos abiertos": la valida la
-- API dentro de una transacción (ver nota al final).
-- ---------------------------------------------------------------------
CREATE TABLE prestamos (
    id                       INT      NOT NULL AUTO_INCREMENT,
    usuario_id               INT      NOT NULL,   -- quien recibe el activo
    activo_id                INT      NOT NULL,
    entregado_por            INT,                 -- operador que entrega (NULL si aún no hay login)
    recibido_por             INT,                 -- operador que recibe la devolución
    fecha_prestamo           DATETIME(6) NOT NULL,
    fecha_vencimiento        DATETIME(6) NOT NULL,   -- fecha límite de devolución
    fecha_devolucion         DATETIME(6),            -- NULL = préstamo abierto
    observaciones_entrega    TEXT,
    observaciones_devolucion TEXT,                -- p. ej. daños detectados
    created_at               DATETIME(6) NOT NULL,   -- UTC, la pone la API
    updated_at               DATETIME(6) NOT NULL,   -- UTC, la pone la API
    PRIMARY KEY (id),
    CONSTRAINT fk_prestamos_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id) ON DELETE RESTRICT,
    CONSTRAINT fk_prestamos_activo FOREIGN KEY (activo_id)
        REFERENCES activos (id) ON DELETE RESTRICT,
    CONSTRAINT fk_prestamos_entregado_por FOREIGN KEY (entregado_por)
        REFERENCES usuarios (id) ON DELETE RESTRICT,
    CONSTRAINT fk_prestamos_recibido_por FOREIGN KEY (recibido_por)
        REFERENCES usuarios (id) ON DELETE RESTRICT,
    CONSTRAINT chk_prestamos_vencimiento CHECK (fecha_vencimiento > fecha_prestamo),
    CONSTRAINT chk_prestamos_devolucion
        CHECK (fecha_devolucion IS NULL OR fecha_devolucion >= fecha_prestamo)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Datos iniciales (valores de ejemplo: ajústalos a la política real)
-- ---------------------------------------------------------------------
INSERT INTO tipos_usuario (codigo, descripcion, max_prestamos_activos, dias_max_prestamo) VALUES
    ('estudiante',  'Estudiante',  1, 3),
    ('docente',     'Docente',     3, 15),
    ('funcionario', 'Funcionario', 2, 7);

INSERT INTO roles (codigo, descripcion) VALUES
    ('admin',    'Administra usuarios, activos y préstamos'),
    ('operador', 'Entrega y recibe activos'),
    ('consulta', 'Solo lectura');

-- ---------------------------------------------------------------------
-- NOTA para la Fase 2: activos.estado = 'prestado' repite información que
-- ya está en prestamos (un préstamo abierto). Al prestar o devolver, la API
-- debe actualizar prestamos y activos en la MISMA transacción.
-- ---------------------------------------------------------------------

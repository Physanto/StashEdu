-- Esquema inicial de usuarios y activos.
-- Ejecutar sobre una base vacía después de 01_configuracion.sql.
USE prestamos_activos;
SET SESSION time_zone = '+00:00';

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Revisión de esquema: 2610dce06348.

CREATE TABLE activos (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    codigo_inventario VARCHAR(30) NOT NULL, 
    nombre VARCHAR(100) NOT NULL, 
    categoria VARCHAR(30) NOT NULL, 
    marca VARCHAR(60), 
    modelo VARCHAR(60), 
    numero_serie VARCHAR(60), 
    descripcion TEXT, 
    estado VARCHAR(20) NOT NULL, 
    fecha_adquisicion DATE, 
    created_at DATETIME(6) NOT NULL, 
    updated_at DATETIME(6) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (codigo_inventario), 
    UNIQUE (numero_serie)
);

CREATE TABLE usuarios (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    nombre_completo VARCHAR(120) NOT NULL, 
    documento VARCHAR(20) NOT NULL, 
    email VARCHAR(120) NOT NULL, 
    telefono VARCHAR(20), 
    tipo_usuario VARCHAR(20) NOT NULL, 
    activo BOOL NOT NULL, 
    created_at DATETIME(6) NOT NULL, 
    updated_at DATETIME(6) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (documento), 
    UNIQUE (email)
);

INSERT INTO alembic_version (version_num) VALUES ('2610dce06348');

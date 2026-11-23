"""Integración contra MySQL/MariaDB real (opcional): concurrencia, rollback y migraciones.

SQLite no tiene bloqueos de fila (FOR UPDATE), así que las carreras entre dos
peticiones solo se pueden probar en el motor de verdad. Se usa un esquema
temporal con nombre aleatorio que se borra al terminar; nunca DB_NAME.

Linux/macOS: RUN_MYSQL_TESTS=1 python -m unittest tests.test_mysql_integration -v
PowerShell:  $env:RUN_MYSQL_TESTS='1'; python -m unittest tests.test_mysql_integration -v
El usuario de .env necesita permiso para crear y borrar bases `test_%`.
"""

import os
import re
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from flask_migrate import downgrade, upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.auth import emitir_token
from app.extensions import db
from app.models import Activo, Prestamo, Usuario
from app.security import hash_password
from config import Config

ROL_ADMIN, ROL_OPERADOR = 1, 2  # ids sembrados por la migración de la Fase 3
DOCENTE = 2  # tipo sembrado por la migración de la Fase 1


@unittest.skipUnless(os.getenv("RUN_MYSQL_TESTS") == "1", "Integración MySQL opcional")
class MySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = "test_stashedu_" + uuid.uuid4().hex
        assert re.fullmatch(r"test_stashedu_[a-f0-9]{32}", cls.schema)
        cls.servidor = create_engine(
            Config.SQLALCHEMY_DATABASE_URI.set(database=""), pool_pre_ping=True
        )
        with cls.servidor.begin() as conexion:
            conexion.execute(text(f"CREATE DATABASE `{cls.schema}` CHARACTER SET utf8mb4"))
        cls.addClassCleanup(cls.borrar_esquema)

        class ConfigAislada(Config):
            TESTING = True
            SECRET_KEY = "test-only-secret-key-with-at-least-32-characters"
            SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI.set(database=cls.schema)

        cls.app = create_app(ConfigAislada)
        with cls.app.app_context():
            # Migración con datos previos: una cuenta del autoregistro anterior
            # (contraseña sin rol) no cumple el CHECK de la Fase 3.
            upgrade(revision="20261008_02")
            db.session.execute(text(
                "INSERT INTO usuarios (id, nombre_completo, documento, email, tipo_usuario_id,"
                " password_hash, habilitado, created_at, updated_at) VALUES (99, 'Histórico',"
                " '099', 'legacy@example.com', 2, 'scrypt:legacy', 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))"
            ))
            db.session.commit()
            upgrade()
            legado = db.session.get(Usuario, 99)
            assert legado.password_hash is None and legado.rol_id is None
            db.session.remove()
        cls.fixture_hash = hash_password("Clave de pruebas 123")

    @classmethod
    def borrar_esquema(cls):
        try:
            if getattr(cls, "app", None) is not None:
                with cls.app.app_context():
                    db.session.remove()
                    db.engine.dispose()
        finally:
            assert re.fullmatch(r"test_stashedu_[a-f0-9]{32}", cls.schema)
            with cls.servidor.begin() as conexion:
                conexion.execute(text(f"DROP DATABASE `{cls.schema}`"))
            cls.servidor.dispose()

    def setUp(self):
        with self.app.app_context():
            for modelo in (Prestamo, Activo, Usuario):
                db.session.execute(db.delete(modelo))
            cuenta = {"tipo_usuario_id": DOCENTE, "password_hash": self.fixture_hash}
            db.session.add_all([
                Usuario(id=1, nombre_completo="Admin", documento="001", email="admin@example.com", rol_id=ROL_ADMIN, **cuenta),
                Usuario(id=2, nombre_completo="Operador", documento="002", email="op@example.com", rol_id=ROL_OPERADOR, **cuenta),
                Usuario(id=3, nombre_completo="Ana", documento="003", email="ana@example.com", tipo_usuario_id=DOCENTE),
                Usuario(id=4, nombre_completo="Luis", documento="004", email="luis@example.com", tipo_usuario_id=DOCENTE),
                Activo(id=1, codigo_inventario="A1", nombre="Portátil", categoria="portatil"),
            ])
            db.session.commit()
            self.tokens = {i: emitir_token(db.session.get(Usuario, i)) for i in (1, 2)}

    def peticion(self, metodo, ruta, cuerpo=None, cuenta=2):
        with self.app.test_client() as cliente:
            return cliente.open(
                ruta, method=metodo, json=cuerpo,
                headers={"Authorization": "Bearer " + self.tokens[cuenta]},
            )

    def prestar(self, usuario_id=3, cuenta=2):
        return self.peticion("POST", "/api/v1/prestamos", {"usuario_id": usuario_id, "activo_id": 1, "dias": 5}, cuenta)

    def carrera(self, primera, segunda):
        """Lanza dos peticiones a la vez y devuelve sus códigos HTTP en orden."""
        barrera = Barrier(2)

        def correr(accion):
            barrera.wait(timeout=10)
            return accion().status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(correr, (primera, segunda)))

    def test_two_loans_of_the_same_asset(self):
        resultado = self.carrera(lambda: self.prestar(3, 2), lambda: self.prestar(4, 1))
        self.assertEqual(sorted(resultado), [201, 409])
        with self.app.app_context():
            self.assertEqual(db.session.scalar(db.select(db.func.count(Prestamo.id))), 1)
            self.assertEqual(db.session.get(Activo, 1).estado, "prestado")

    def test_two_returns_of_the_same_loan(self):
        prestamo = self.prestar().json
        ruta = f"/api/v1/prestamos/{prestamo['id']}/devolucion"
        resultado = self.carrera(lambda: self.peticion("POST", ruta, {}, 2), lambda: self.peticion("POST", ruta, {}, 1))
        self.assertEqual(sorted(resultado), [200, 409])
        with self.app.app_context():
            self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
            self.assertIsNotNone(db.session.get(Prestamo, prestamo["id"]).fecha_devolucion)

    def test_loan_vs_asset_write_off(self):
        resultado = self.carrera(lambda: self.prestar(), lambda: self.peticion("DELETE", "/api/v1/activos/1", cuenta=1))
        self.assertIn(resultado, ([201, 409], [409, 204]))
        with self.app.app_context():
            activo = db.session.get(Activo, 1)
            total = db.session.scalar(db.select(db.func.count(Prestamo.id)))
            esperado = ("prestado", 1) if resultado[0] == 201 else ("baja", 0)
            self.assertEqual((activo.estado, total), esperado)

    def test_loan_vs_user_deactivation(self):
        resultado = self.carrera(lambda: self.prestar(), lambda: self.peticion("DELETE", "/api/v1/usuarios/3", cuenta=1))
        self.assertIn(resultado, ([201, 409], [409, 204]))
        with self.app.app_context():
            ana = db.session.get(Usuario, 3)
            pendiente = db.session.scalar(
                db.select(Prestamo.id).where(Prestamo.usuario_id == 3, Prestamo.fecha_devolucion.is_(None))
            )
            # Nunca queda un usuario deshabilitado con un préstamo sin devolver.
            self.assertFalse(pendiente and not ana.habilitado)

    def test_failed_loan_rolls_back_everything(self):
        with patch.object(db.session, "commit", side_effect=RuntimeError("fallo simulado")), \
                self.assertLogs(self.app.logger, level="ERROR"):
            self.assertEqual(self.prestar().status_code, 500)
        with self.app.app_context():
            self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
            self.assertEqual(db.session.scalar(db.select(db.func.count(Prestamo.id))), 0)

    def test_failed_return_rolls_back_everything(self):
        prestamo = self.prestar().json
        with patch.object(db.session, "commit", side_effect=RuntimeError("fallo simulado")), \
                self.assertLogs(self.app.logger, level="ERROR"):
            respuesta = self.peticion("POST", f"/api/v1/prestamos/{prestamo['id']}/devolucion", {})
            self.assertEqual(respuesta.status_code, 500)
        with self.app.app_context():
            self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
            self.assertIsNone(db.session.get(Prestamo, prestamo["id"]).fecha_devolucion)

    def test_check_constraint_is_a_client_error(self):
        # MariaDB informa la violación de un CHECK como OperationalError: debe ser 400, no 503.
        with self.app.app_context():
            with self.assertRaises(Exception) as contexto:
                db.session.execute(text("UPDATE activos SET estado = 'perdido' WHERE id = 1"))
            from app.errors import CODIGOS_CHECK, _codigo_mysql

            self.assertIn(_codigo_mysql(contexto.exception), CODIGOS_CHECK)
            db.session.rollback()

    def test_phase_3_migration_downgrade_and_upgrade(self):
        with self.app.app_context():
            db.session.remove()
            downgrade(revision="20261008_02")
            upgrade()
            self.assertEqual(db.session.get(Usuario, 3).email, "ana@example.com")
            # Las cuentas pierden el rol al bajar: el CHECK obliga a quitar también el hash.
            self.assertIsNone(db.session.get(Usuario, 1).password_hash)

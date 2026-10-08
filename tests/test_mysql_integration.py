"""Integración opt-in sobre un esquema MySQL temporal, jamás la BD de la aplicación.

PowerShell: $env:RUN_MYSQL_TESTS='1'; python -m unittest tests.test_mysql_integration -v
Requiere CREATE/DROP DATABASE para el usuario configurado en .env.
"""

import os
import re
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from flask_migrate import downgrade, upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.auth import emitir_token
from app.extensions import db
from app.models import Activo, Prestamo, Usuario
from app.models.mixins import _ahora
from app.security import hash_password
from config import Config


@unittest.skipUnless(os.getenv("RUN_MYSQL_TESTS") == "1", "MySQL integration is opt-in")
class MySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = "stashedu_test_" + uuid.uuid4().hex
        assert re.fullmatch(r"stashedu_test_[a-f0-9]{32}", cls.schema)
        cls.admin = create_engine(
            Config.SQLALCHEMY_DATABASE_URI.set(database=None), pool_pre_ping=True
        )
        try:
            with cls.admin.begin() as connection:
                connection.execute(
                    text(f"CREATE DATABASE `{cls.schema}` CHARACTER SET utf8mb4")
                )
        except Exception:
            cls.admin.dispose()
            raise
        cls.addClassCleanup(cls.cleanup_schema)

        class IsolatedConfig(Config):
            TESTING = True
            SECRET_KEY = "test-only-secret-key-with-at-least-32-characters"
            SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI.set(
                database=cls.schema
            )
            API_OPERATOR_IDS = (1, 2)

        cls.app = create_app(IsolatedConfig)
        with cls.app.app_context():
            # Comprobar upgrade desde fase 1 con un usuario histórico sin contraseña.
            upgrade(revision="2610dce06348")
            db.session.execute(
                text(
                    "INSERT INTO usuarios (id,nombre_completo,documento,email,tipo_usuario,activo,created_at,updated_at) VALUES (1,'Histórico','001','legacy@example.com','docente',1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))"
                )
            )
            db.session.commit()
            upgrade()
            legacy = db.session.get(Usuario, 1)
            assert legacy.email == "legacy@example.com" and legacy.password_hash is None
            db.session.remove()
        cls.fixture_hash = hash_password("Test password seguro")

    @classmethod
    def cleanup_schema(cls):
        try:
            try:
                if getattr(cls, "app", None) is not None:
                    with cls.app.app_context():
                        db.session.remove()
                        db.engine.dispose()
            finally:
                # Solo borrar el esquema aleatorio creado por esta clase, nunca DB_NAME.
                assert re.fullmatch(r"stashedu_test_[a-f0-9]{32}", cls.schema)
                with cls.admin.begin() as connection:
                    connection.execute(text(f"DROP DATABASE `{cls.schema}`"))
        finally:
            cls.admin.dispose()

    def setUp(self):
        with self.app.app_context():
            for model in (Prestamo, Activo, Usuario):
                db.session.execute(db.delete(model))
            db.session.add_all(
                [
                    Usuario(
                        id=1,
                        nombre_completo="Ana",
                        documento="001",
                        email="ana@example.com",
                        tipo_usuario="docente",
                        password_hash=self.fixture_hash,
                    ),
                    Usuario(
                        id=2,
                        nombre_completo="Luis",
                        documento="002",
                        email="luis@example.com",
                        tipo_usuario="docente",
                        password_hash=self.fixture_hash,
                    ),
                    Activo(
                        id=1,
                        codigo_inventario="A1",
                        nombre="Portátil",
                        categoria="portatil",
                    ),
                ]
            )
            db.session.commit()
            self.tokens = {i: emitir_token(db.session.get(Usuario, i)) for i in (1, 2)}

    def request(self, method, path, body=None, user=1):
        with self.app.test_client() as client:
            return client.open(
                path,
                method=method,
                json=body,
                headers={"Authorization": "Bearer " + self.tokens[user]},
            )

    def loan_body(self, user=1):
        return {
            "usuario_id": user,
            "activo_id": 1,
            "fecha_devolucion_prevista": (_ahora() + timedelta(days=7)).isoformat()
            + "Z",
        }

    def race(self, first, second):
        barrier = Barrier(2)

        def run(action):
            barrier.wait(timeout=10)
            return action().status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, (first, second)))

    def test_concurrent_creation(self):
        result = self.race(
            lambda: self.request("POST", "/api/v1/prestamos", self.loan_body(1), 1),
            lambda: self.request("POST", "/api/v1/prestamos", self.loan_body(2), 2),
        )
        self.assertEqual(sorted(result), [201, 409])
        with self.app.app_context():
            self.assertEqual(
                db.session.scalar(db.select(db.func.count(Prestamo.id))), 1
            )
            self.assertEqual(db.session.get(Activo, 1).estado, "prestado")

    def test_concurrent_returns(self):
        loan = self.request("POST", "/api/v1/prestamos", self.loan_body()).json
        path = f"/api/v1/prestamos/{loan['id']}/devolucion"
        result = self.race(
            lambda: self.request("POST", path, {}),
            lambda: self.request("POST", path, {}, 2),
        )
        self.assertEqual(sorted(result), [200, 409])
        with self.app.app_context():
            self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
            self.assertIsNotNone(db.session.get(Prestamo, loan["id"]).fecha_devolucion)

    def test_loan_vs_asset_deletion(self):
        result = self.race(
            lambda: self.request("POST", "/api/v1/prestamos", self.loan_body()),
            lambda: self.request("DELETE", "/api/v1/activos/1", user=2),
        )
        self.assertIn(result, ([201, 409], [409, 204]))
        with self.app.app_context():
            asset = db.session.get(Activo, 1)
            count = db.session.scalar(db.select(db.func.count(Prestamo.id)))
            self.assertEqual(
                (asset.estado, count),
                ("prestado", 1) if result[0] == 201 else ("baja", 0),
            )

    def test_loan_vs_user_deactivation(self):
        result = self.race(
            lambda: self.request("POST", "/api/v1/prestamos", self.loan_body()),
            lambda: self.request("DELETE", "/api/v1/usuarios/1", user=2),
        )
        # La autenticación también puede rechazar al usuario ya desactivado.
        self.assertIn(result, ([201, 409], [409, 204], [401, 204]))
        with self.app.app_context():
            outstanding = db.session.scalar(
                db.select(Prestamo.id).where(
                    Prestamo.usuario_id == 1, Prestamo.fecha_devolucion.is_(None)
                )
            )
            if outstanding:
                self.assertTrue(db.session.get(Usuario, 1).activo)

    def test_failed_transaction_and_migration_downgrade(self):
        with (
            patch.object(
                db.session, "commit", side_effect=RuntimeError("simulated failure")
            ),
            self.assertLogs(self.app.logger, level="ERROR"),
        ):
            self.assertEqual(
                self.request("POST", "/api/v1/prestamos", self.loan_body()).status_code,
                500,
            )
        with self.app.app_context():
            self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
            self.assertEqual(
                db.session.scalar(db.select(db.func.count(Prestamo.id))), 0
            )
            db.session.remove()
            downgrade(revision="2610dce06348")
            upgrade()
            self.assertEqual(db.session.get(Usuario, 1).email, "ana@example.com")

    def test_return_rollback(self):
        loan = self.request("POST", "/api/v1/prestamos", self.loan_body()).json
        with (
            patch.object(
                db.session,
                "commit",
                side_effect=RuntimeError("simulated return failure"),
            ),
            self.assertLogs(self.app.logger, level="ERROR"),
        ):
            self.assertEqual(
                self.request(
                    "POST", f"/api/v1/prestamos/{loan['id']}/devolucion", {}
                ).status_code,
                500,
            )
        with self.app.app_context():
            self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
            self.assertIsNone(db.session.get(Prestamo, loan["id"]).fecha_devolucion)

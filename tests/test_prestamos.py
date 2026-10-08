import unittest
from datetime import timedelta
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import Activo, Prestamo, Usuario
from app.models.mixins import _ahora


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY = "test-only-secret-key-with-at-least-32-characters"
    AUTH_TOKEN_MAX_AGE = 3600
    API_OPERATOR_IDS = (1,)


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()
        db.session.add_all([
            Usuario(nombre_completo="Ana", documento="001", email="ana@example.com", tipo_usuario="docente"),
            Activo(codigo_inventario="A1", nombre="Portátil", categoria="portatil"),
        ])
        db.session.commit()
        from app.auth import emitir_token
        from app.security import hash_password
        if not hasattr(APITestCase, "fixture_hash"):
            APITestCase.fixture_hash = hash_password("Test password seguro")
        db.session.get(Usuario, 1).password_hash = APITestCase.fixture_hash
        db.session.commit()
        self.client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + emitir_token(db.session.get(Usuario, 1))

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def loan(self, **changes):
        body = {"usuario_id": 1, "activo_id": 1, "fecha_devolucion_prevista": (_ahora() + timedelta(days=7)).isoformat() + "Z"}
        body.update(changes)
        return self.client.post("/api/v1/prestamos", json=body)


class LoanTests(APITestCase):
    def test_create_and_history(self):
        response = self.loan()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["estado"], "activo")
        self.assertIsNone(response.json["fecha_devolucion"])
        self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
        self.assertEqual(self.client.get("/api/v1/prestamos").json["meta"]["total"], 1)
        self.assertEqual(self.client.get("/api/v1/prestamos/1").status_code, 200)

    def test_double_loan_and_state_protection(self):
        self.assertEqual(self.loan().status_code, 201)
        self.assertEqual(self.loan().status_code, 409)
        self.assertEqual(self.client.patch("/api/v1/activos/1", json={"estado": "disponible"}).status_code, 409)
        self.assertEqual(self.client.delete("/api/v1/activos/1").status_code, 409)
        self.assertEqual(self.client.delete("/api/v1/usuarios/1").status_code, 409)
        self.assertEqual(self.client.patch("/api/v1/usuarios/1", json={"activo": False}).status_code, 409)
        self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
        self.assertTrue(db.session.get(Usuario, 1).activo)

    def test_invalid_ids_and_dates(self):
        for value in [True, 0, -1, "1", 1.1, [], None]:
            with self.subTest(value=value):
                self.assertEqual(self.loan(usuario_id=value).status_code, 400)
        for value in ["2020-01-01T00:00:00Z", "2099-01-01", "2099-01-01T00:00:00", "invalid", {}, None]:
            with self.subTest(value=value):
                self.assertEqual(self.loan(fecha_devolucion_prevista=value).status_code, 400)
        self.assertEqual(db.session.scalar(db.select(db.func.count(Prestamo.id))), 0)

    def test_unavailable_and_missing(self):
        self.assertEqual(self.loan(usuario_id=99).status_code, 404)
        self.assertEqual(self.loan(activo_id=99).status_code, 404)
        for state in ("mantenimiento", "baja"):
            db.session.get(Activo, 1).estado = state
            db.session.commit()
            self.assertEqual(self.loan().status_code, 409)
        db.session.add(Usuario(nombre_completo="Inactivo", documento="003", email="off@example.com", tipo_usuario="estudiante", activo=False))
        db.session.commit()
        self.assertEqual(self.loan(usuario_id=2).status_code, 409)

    def test_failed_insert_rolls_back_reservation(self):
        with patch.object(db.session, "commit", side_effect=RuntimeError("simulated commit failure")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                self.assertEqual(self.loan().status_code, 500)
        self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
        self.assertEqual(db.session.scalar(db.select(db.func.count(Prestamo.id))), 0)

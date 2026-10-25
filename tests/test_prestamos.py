import unittest
from datetime import timedelta
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import Activo, Prestamo, TipoUsuario, Usuario
from app.models.mixins import _ahora


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()
        db.session.add_all([
            TipoUsuario(codigo="estudiante", descripcion="Estudiante", max_prestamos_activos=1, dias_max_prestamo=3),
            TipoUsuario(codigo="docente", descripcion="Docente", max_prestamos_activos=3, dias_max_prestamo=15),
        ])
        db.session.add_all([
            Usuario(nombre_completo="Ana", documento="001", email="ana@example.com", tipo_usuario_id=2),
            Activo(codigo_inventario="A1", nombre="Portátil", categoria="portatil"),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def loan(self, **changes):
        body = {"usuario_id": 1, "activo_id": 1, "dias": 7}
        body.update(changes)
        return self.client.post("/api/v1/prestamos", json=body)

    def add_asset(self, codigo):
        activo = Activo(codigo_inventario=codigo, nombre="Equipo", categoria="otro")
        db.session.add(activo)
        db.session.commit()
        return activo.id


class LoanTests(APITestCase):
    def test_create_and_history(self):
        response = self.loan(observaciones_entrega="Con cargador")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["estado"], "activo")
        self.assertEqual(response.json["dias_retraso"], 0)
        self.assertEqual(response.json["usuario"]["id"], 1)
        self.assertEqual(response.json["activo"]["codigo_inventario"], "A1")
        self.assertEqual(response.json["observaciones_entrega"], "Con cargador")
        self.assertIsNone(response.json["fecha_devolucion"])
        self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
        prestamo = db.session.get(Prestamo, 1)
        self.assertEqual(prestamo.fecha_vencimiento - prestamo.fecha_prestamo, timedelta(days=7))
        self.assertEqual(self.client.get("/api/v1/prestamos").json["meta"]["total"], 1)
        self.assertEqual(self.client.get("/api/v1/prestamos/1").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/prestamos/99").status_code, 404)

    def test_default_days_come_from_user_type(self):
        response = self.loan(dias=None)
        self.assertEqual(response.status_code, 201)
        prestamo = db.session.get(Prestamo, 1)
        self.assertEqual(prestamo.fecha_vencimiento - prestamo.fecha_prestamo, timedelta(days=15))

    def test_days_above_user_type_limit(self):
        self.assertEqual(self.loan(dias=16).status_code, 400)
        self.assertEqual(db.session.get(Activo, 1).estado, "disponible")

    def test_max_open_loans_per_user_type(self):
        db.session.get(Usuario, 1).tipo_usuario_id = 1  # estudiante: máximo 1
        db.session.commit()
        segundo = self.add_asset("A2")
        self.assertEqual(self.loan(dias=3).status_code, 201)
        self.assertEqual(self.loan(activo_id=segundo, dias=3).status_code, 409)
        self.assertEqual(db.session.get(Activo, segundo).estado, "disponible")
        self.client.post("/api/v1/prestamos/1/devolucion")
        self.assertEqual(self.loan(activo_id=segundo, dias=3).status_code, 201)

    def test_double_loan_and_state_protection(self):
        self.assertEqual(self.loan().status_code, 201)
        self.assertEqual(self.loan().status_code, 409)
        self.assertEqual(self.client.patch("/api/v1/activos/1", json={"estado": "disponible"}).status_code, 409)
        self.assertEqual(self.client.patch("/api/v1/activos/1", json={"marca": "Lenovo"}).status_code, 200)
        self.assertEqual(self.client.delete("/api/v1/activos/1").status_code, 409)
        self.assertEqual(self.client.delete("/api/v1/usuarios/1").status_code, 409)
        self.assertEqual(self.client.patch("/api/v1/usuarios/1", json={"habilitado": False}).status_code, 409)
        self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
        self.assertTrue(db.session.get(Usuario, 1).habilitado)

    def test_invalid_body(self):
        for value in [True, 0, -1, "1", 1.1, [], None]:
            with self.subTest(usuario_id=value):
                self.assertEqual(self.loan(usuario_id=value).status_code, 400)
        for value in [True, 0, -1, "7", 1.5, []]:
            with self.subTest(dias=value):
                self.assertEqual(self.loan(dias=value).status_code, 400)
        self.assertEqual(self.loan(observaciones_entrega="x" * 1001).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/prestamos", data="texto").status_code, 400)
        self.assertEqual(db.session.scalar(db.select(db.func.count(Prestamo.id))), 0)

    def test_unavailable_and_missing(self):
        self.assertEqual(self.loan(usuario_id=99).status_code, 404)
        self.assertEqual(self.loan(activo_id=99).status_code, 404)
        for state in ("mantenimiento", "baja"):
            db.session.get(Activo, 1).estado = state
            db.session.commit()
            self.assertEqual(self.loan().status_code, 409)
        db.session.get(Activo, 1).estado = "disponible"
        db.session.get(Usuario, 1).habilitado = False
        db.session.commit()
        self.assertEqual(self.loan().status_code, 409)

    def test_failed_insert_rolls_back_reservation(self):
        with patch.object(db.session, "commit", side_effect=RuntimeError("simulated commit failure")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                self.assertEqual(self.loan().status_code, 500)
        self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
        self.assertEqual(db.session.scalar(db.select(db.func.count(Prestamo.id))), 0)


if __name__ == "__main__":
    unittest.main()

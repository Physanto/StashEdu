from unittest.mock import patch

from app.extensions import db
from app.models import Activo, Prestamo
from tests.test_prestamos import APITestCase


class ReturnTests(APITestCase):
    def test_return_reloan_and_history(self):
        self.assertEqual(self.loan().status_code, 201)
        response = self.client.post("/api/v1/prestamos/1/devolucion", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["estado"], "devuelto")
        returned_at = response.json["fecha_devolucion"]
        self.assertIsNotNone(returned_at)
        self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
        self.assertEqual(
            self.client.post("/api/v1/prestamos/1/devolucion", json={}).status_code, 409
        )
        self.assertEqual(
            self.client.get("/api/v1/prestamos/1").json["fecha_devolucion"], returned_at
        )
        self.assertEqual(self.loan().status_code, 201)
        self.assertEqual(self.client.get("/api/v1/prestamos").json["meta"]["total"], 2)

    def test_missing_invalid_and_inconsistent(self):
        self.assertEqual(
            self.client.post("/api/v1/prestamos/99/devolucion", json={}).status_code,
            404,
        )
        self.loan()
        self.assertEqual(
            self.client.post(
                "/api/v1/prestamos/1/devolucion", json={"estado": "baja"}
            ).status_code,
            400,
        )
        db.session.get(Activo, 1).estado = "baja"
        db.session.commit()
        self.assertEqual(
            self.client.post("/api/v1/prestamos/1/devolucion", json={}).status_code, 409
        )
        self.assertIsNone(db.session.get(Prestamo, 1).fecha_devolucion)

    def test_return_rollback(self):
        self.loan()
        with (
            patch.object(
                db.session,
                "commit",
                side_effect=RuntimeError("simulated return failure"),
            ),
            self.assertLogs(self.app.logger, level="ERROR"),
        ):
            self.assertEqual(
                self.client.post("/api/v1/prestamos/1/devolucion", json={}).status_code,
                500,
            )
        self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
        self.assertIsNone(db.session.get(Prestamo, 1).fecha_devolucion)

    def test_logical_deletion_after_return_preserves_history(self):
        self.loan()
        self.client.post("/api/v1/prestamos/1/devolucion", json={})
        self.assertEqual(self.client.delete("/api/v1/activos/1").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/usuarios/1").status_code, 204)
        from app.auth import emitir_token
        from app.models import Usuario

        user = Usuario(
            nombre_completo="Operador",
            documento="002",
            email="op@example.com",
            tipo_usuario="funcionario",
            password_hash=self.fixture_hash,
        )
        db.session.add(user)
        db.session.commit()
        self.app.config["API_OPERATOR_IDS"] = (2,)
        self.client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + emitir_token(user)
        self.assertEqual(self.client.get("/api/v1/prestamos/1").status_code, 200)

from datetime import timedelta
from unittest.mock import patch

from app.extensions import db
from app.models import Activo, Prestamo
from app.models.mixins import _ahora
from tests.test_prestamos import APITestCase


class ReturnTests(APITestCase):
    def test_return_reloan_and_history(self):
        self.assertEqual(self.loan().status_code, 201)
        response = self.client.post(
            "/api/v1/prestamos/1/devolucion", json={"observaciones_devolucion": "Sin daños"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["estado"], "devuelto")
        self.assertEqual(response.json["observaciones_devolucion"], "Sin daños")
        returned_at = response.json["fecha_devolucion"]
        self.assertIsNotNone(returned_at)
        self.assertEqual(db.session.get(Activo, 1).estado, "disponible")
        self.assertEqual(self.client.post("/api/v1/prestamos/1/devolucion").status_code, 409)
        self.assertEqual(self.client.get("/api/v1/prestamos/1").json["fecha_devolucion"], returned_at)
        self.assertEqual(self.loan().status_code, 201)
        self.assertEqual(self.client.get("/api/v1/prestamos").json["meta"]["total"], 2)

    def test_late_return(self):
        self.loan()
        prestamo = db.session.get(Prestamo, 1)
        prestamo.fecha_prestamo = _ahora() - timedelta(days=10)
        prestamo.fecha_vencimiento = _ahora() - timedelta(days=2, hours=1)
        db.session.commit()
        self.assertEqual(self.client.get("/api/v1/prestamos/1").json["estado"], "vencido")
        response = self.client.post("/api/v1/prestamos/1/devolucion")
        self.assertEqual(response.json["estado"], "devuelto_con_retraso")
        self.assertEqual(response.json["dias_retraso"], 3)

    def test_missing_invalid_and_inconsistent(self):
        self.assertEqual(self.client.post("/api/v1/prestamos/99/devolucion").status_code, 404)
        self.loan()
        self.assertEqual(self.client.post("/api/v1/prestamos/1/devolucion", data="texto").status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/v1/prestamos/1/devolucion", json={"observaciones_devolucion": 5}
            ).status_code,
            400,
        )
        db.session.get(Activo, 1).estado = "baja"
        db.session.commit()
        self.assertEqual(self.client.post("/api/v1/prestamos/1/devolucion").status_code, 409)
        self.assertIsNone(db.session.get(Prestamo, 1).fecha_devolucion)

    def test_return_rollback(self):
        self.loan()
        with patch.object(db.session, "commit", side_effect=RuntimeError("simulated return failure")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                self.assertEqual(self.client.post("/api/v1/prestamos/1/devolucion").status_code, 500)
        self.assertEqual(db.session.get(Activo, 1).estado, "prestado")
        self.assertIsNone(db.session.get(Prestamo, 1).fecha_devolucion)

    def test_logical_deletion_after_return_preserves_history(self):
        self.loan()
        self.client.post("/api/v1/prestamos/1/devolucion")
        self.assertEqual(self.client.delete("/api/v1/usuarios/1").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/activos/1").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/prestamos/1").status_code, 200)

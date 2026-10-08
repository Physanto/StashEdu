import json

from app.extensions import db
from app.models import Activo, Prestamo
from tests.test_prestamos import APITestCase


class ValidationTests(APITestCase):
    def test_json_content_and_shape(self):
        for body in ([], None, "text", 7, True):
            with self.subTest(body=body):
                response = self.client.post(
                    "/api/v1/usuarios",
                    data=json.dumps(body),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post("/api/v1/usuarios", data="{").status_code, 415
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/usuarios", data="{", content_type="application/json"
            ).status_code,
            400,
        )
        oversized = json.dumps({"descripcion": "a" * 65536})
        self.assertEqual(
            self.client.post(
                "/api/v1/activos", data=oversized, content_type="application/json"
            ).status_code,
            413,
        )

    def test_unknown_fields_empty_patches_and_null_required(self):
        for route in ("usuarios", "activos"):
            self.assertEqual(
                self.client.patch(f"/api/v1/{route}/1", json={}).status_code, 400
            )
            self.assertEqual(
                self.client.patch(
                    f"/api/v1/{route}/1", json={"unknown": 123}
                ).status_code,
                400,
            )
        self.assertEqual(self.loan(estado="devuelto").status_code, 400)
        self.assertEqual(
            self.client.patch("/api/v1/usuarios/1", json={"email": None}).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch("/api/v1/activos/1", json={"nombre": " "}).status_code,
            400,
        )

    def test_types_enums_lengths_and_dates(self):
        for data in (
            {"activo": 1},
            {"nombre_completo": []},
            {"tipo_usuario": "admin"},
            {"nombre_completo": "a" * 121},
            {"email": "invalid"},
        ):
            self.assertEqual(
                self.client.patch("/api/v1/usuarios/1", json=data).status_code, 400
            )
        for data in (
            {"estado": "prestado"},
            {"categoria": {}},
            {"descripcion": "a" * 10001},
            {"fecha_adquisicion": "2026-02-30"},
            {"fecha_adquisicion": "20261008"},
        ):
            self.assertEqual(
                self.client.patch("/api/v1/activos/1", json=data).status_code, 400
            )
        self.assertEqual(
            self.client.patch(
                "/api/v1/activos/1", json={"fecha_adquisicion": None, "marca": " "}
            ).status_code,
            200,
        )
        self.assertIsNone(db.session.get(Activo, 1).marca)

    def test_pagination_invalid_queries_and_ids(self):
        for route in ("usuarios", "activos", "prestamos"):
            for query in (
                "page=0",
                "page=-1",
                "page=true",
                "page=1.1",
                "per_page=101",
                "per_page=0",
                "page=1&page=2",
                "unknown=1",
                "page=",
                "page=" + "9" * 100,
            ):
                with self.subTest(route=route, query=query[:30]):
                    self.assertEqual(
                        self.client.get(f"/api/v1/{route}?{query}").status_code, 400
                    )
            response = self.client.get(f"/api/v1/{route}?page=2&per_page=100")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["data"], [])
            self.assertEqual(self.client.get(f"/api/v1/{route}/0").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/auth/me?unknown=1").status_code, 400)

    def test_email_normalized_uniqueness(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "nombre_completo": "Other",
                "documento": "009",
                "email": " ANA@EXAMPLE.COM ",
                "tipo_usuario": "docente",
                "password": "Una contraseña segura",
            },
        )
        self.assertEqual(response.status_code, 409)
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": " ANA@EXAMPLE.COM ", "password": "Test password seguro"},
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_unicode_and_nul_are_client_errors(self):
        for value in ("bad\ud800text", "nul\x00text"):
            self.assertEqual(
                self.client.patch(
                    "/api/v1/usuarios/1", json={"nombre_completo": value}
                ).status_code,
                400,
            )
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/register",
                json={
                    "nombre_completo": "Other",
                    "documento": "009",
                    "email": "other@example.com",
                    "tipo_usuario": "docente",
                    "password": "bad\ud800password-secret",
                },
            ).status_code,
            400,
        )

    def test_timezone_normalized_and_late_returns(self):
        response = self.loan(fecha_devolucion_prevista="2099-12-01T17:00:00-05:00")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json["fecha_devolucion_prevista"], "2099-12-01T22:00:00Z"
        )
        from datetime import timedelta

        from app.models.mixins import _ahora

        loan = db.session.get(Prestamo, response.json["id"])
        loan.fecha_prestamo = _ahora() - timedelta(days=2)
        loan.fecha_devolucion_prevista = _ahora() - timedelta(days=1)
        db.session.commit()
        self.assertTrue(self.client.get("/api/v1/prestamos/1").json["retrasado"])
        self.assertTrue(
            self.client.post("/api/v1/prestamos/1/devolucion", json={}).json[
                "retrasado"
            ]
        )

    def test_http_errors_preserve_contract(self):
        missing = self.client.get("/missing")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.content_type, "application/json")
        method = self.client.put("/api/v1/health", json={})
        self.assertEqual(method.status_code, 405)
        self.assertIn("GET", method.headers["Allow"])
        unauthenticated = self.client.get(
            "/api/v1/usuarios", headers={"Authorization": ""}
        )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.headers["WWW-Authenticate"], "Bearer")

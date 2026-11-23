"""Fase 4: validación de datos y manejo uniforme de errores HTTP."""

from unittest.mock import patch

from app.extensions import db
from app.models import Usuario
from tests.test_prestamos import PASSWORD_PRUEBAS, APITestCase

USUARIO = {"nombre_completo": "Nuevo", "documento": "555", "email": "nuevo@example.com", "tipo_usuario_id": 1}


class BodyValidationTests(APITestCase):
    def test_content_type_and_json_shape(self):
        url = "/api/v1/usuarios"
        self.assertEqual(self.client.post(url, data='{"a": 1}', content_type="text/plain").status_code, 415)
        self.assertEqual(self.client.post(url, data="{malo", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(url, json=[USUARIO]).status_code, 400)
        response = self.client.post(url, data="x")
        self.assertEqual(response.json, {"error": "El Content-Type debe ser application/json."})

    def test_unknown_fields_are_rejected_everywhere(self):
        self.loan()
        casos = (
            ("post", "/api/v1/usuarios", {**USUARIO, "password_hash": "x"}),
            ("post", "/api/v1/usuarios", {**USUARIO, "rol_id": 1}),
            ("patch", "/api/v1/usuarios/1", {"apellido": "Pérez"}),
            ("put", "/api/v1/activos/1", {"codigo_inventario": "A1", "nombre": "P", "categoria": "otro", "color": "rojo"}),
            ("post", "/api/v1/prestamos", {"usuario_id": 1, "activo_id": 1, "fecha_vencimiento": "2030-01-01"}),
            ("post", "/api/v1/prestamos/1/devolucion", {"estado": "devuelto"}),
            ("post", "/api/v1/auth/login", {"email": "a@b.co", "password": "x" * 12, "rol": "admin"}),
            ("post", "/api/v1/auth/register", {"usuario_id": 1, "rol_id": 2, "password": "x" * 12, "habilitado": True}),
        )
        for method, url, body in casos:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, json=body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["error"], "Hay campos no permitidos.")
                self.assertTrue(response.json["detalles"]["campos"])
        self.assertEqual(db.session.get(Usuario, 1).nombre_completo, "Ana")

    def test_empty_patch_and_null_required_fields(self):
        self.assertEqual(self.client.patch("/api/v1/usuarios/1", json={}).status_code, 400)
        self.assertEqual(self.client.patch("/api/v1/activos/1", json={}).status_code, 400)
        self.assertEqual(self.client.patch("/api/v1/usuarios/1", json={"email": None}).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/activos", json={"codigo_inventario": "Z", "nombre": "   ", "categoria": "otro"}).status_code, 400)
        # Un devolución sin cuerpo sigue siendo válida: el cuerpo es opcional.
        self.loan()
        self.assertEqual(self.client.post("/api/v1/prestamos/1/devolucion").status_code, 200)

    def test_text_content_types_and_lengths(self):
        malos = (
            {**USUARIO, "nombre_completo": "Ana\u0000Pérez"},
            {**USUARIO, "nombre_completo": 123},
            {**USUARIO, "nombre_completo": "x" * 121},
            {**USUARIO, "telefono": ["300"]},
            {**USUARIO, "tipo_usuario_id": "1"},
            {**USUARIO, "habilitado": "si"},
            {**USUARIO, "email": "sin-arroba"},
        )
        for body in malos:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/v1/usuarios", json=body).status_code, 400)
        # Una mitad de emoji suelta ("\ud800") es JSON válido pero no se puede guardar.
        crudo = '{"nombre_completo": "\\ud800", "documento": "9", "email": "x@y.co", "tipo_usuario_id": 1}'
        response = self.client.post("/api/v1/usuarios", data=crudo, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unicode", response.json["error"])

    def test_integers_in_body_stay_in_range(self):
        for value in (2_147_483_648, 0, -5, 1.0, "1", True):
            with self.subTest(value=value):
                self.assertEqual(self.loan(usuario_id=value).status_code, 400)
        self.assertEqual(self.loan(dias=10**12).status_code, 400)

    def test_email_is_normalized_and_unique_ignoring_case(self):
        created = self.client.post("/api/v1/usuarios", json={**USUARIO, "email": "  Nuevo@Example.COM "})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["email"], "nuevo@example.com")
        dup = self.client.post("/api/v1/usuarios", json={**USUARIO, "documento": "556", "email": "NUEVO@example.com"})
        self.assertEqual(dup.status_code, 409)
        # El login también ignora mayúsculas.
        self.client.environ_base.pop("HTTP_AUTHORIZATION")
        login = self.client.post("/api/v1/auth/login", json={"email": "ADMIN@Example.com", "password": PASSWORD_PRUEBAS})
        self.assertEqual(login.status_code, 200)


class QueryValidationTests(APITestCase):
    def test_unknown_and_repeated_parameters(self):
        for url in (
            "/api/v1/usuarios?orden=desc",
            "/api/v1/activos?estado=disponible&color=rojo",
            "/api/v1/prestamos?usuario=1",
            "/api/v1/usuarios/1?expand=true",
            "/api/v1/usuarios/1/prestamos?usuario_id=1",
            "/api/v1/roles?x=1",
            "/api/v1/health?debug=1",
            "/api/v1/prestamos?estado=activo&estado=vencido",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 400)
                self.assertIn("parametros", response.json["detalles"])

    def test_declared_filters_still_work(self):
        for url in (
            "/api/v1/usuarios?page=1&per_page=100&tipo_usuario_id=2&habilitado=true",
            "/api/v1/activos?estado=disponible&categoria=portatil",
            "/api/v1/prestamos?estado=pendiente&desde=2026-01-01&hasta=2026-12-31&usuario_id=1&activo_id=1",
            "/api/v1/activos/1/prestamos?estado=pendiente&page=1",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_invalid_values_of_declared_parameters(self):
        for url in (
            "/api/v1/usuarios?page=0",
            "/api/v1/usuarios?page=abc",
            "/api/v1/usuarios?per_page=101",
            "/api/v1/usuarios?per_page=-1",
            "/api/v1/usuarios?tipo_usuario_id=uno",
            "/api/v1/usuarios?habilitado=quizas",
            "/api/v1/prestamos?usuario_id=0",
            "/api/v1/prestamos?desde=20261001",
            "/api/v1/prestamos?hasta=2026-02-30",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 400)

    def test_path_identifiers(self):
        self.assertEqual(self.client.get("/api/v1/usuarios/0").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/activos/99999999999").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/prestamos/2147483647").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/usuarios/abc").status_code, 404)

    def test_authentication_runs_before_parameter_validation(self):
        self.client.environ_base.pop("HTTP_AUTHORIZATION")
        self.assertEqual(self.client.get("/api/v1/usuarios?orden=desc").status_code, 401)


class HTTPErrorTests(APITestCase):
    def test_framework_errors_are_json_in_spanish(self):
        response = self.client.get("/api/v1/no-existe")
        self.assertEqual((response.status_code, response.json), (404, {"error": "Recurso no encontrado."}))
        response = self.client.delete("/api/v1/prestamos/1")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json["error"], "Método no permitido para este recurso.")
        self.assertIn("GET", response.headers["Allow"])

    def test_body_too_large(self):
        response = self.client.post(
            "/api/v1/activos",
            json={"codigo_inventario": "Z", "nombre": "x" * (70 * 1024), "categoria": "otro"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.content_type, "application/json")

    def test_unauthorized_includes_bearer_challenge(self):
        self.client.environ_base.pop("HTTP_AUTHORIZATION")
        response = self.client.get("/api/v1/activos")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_database_constraint_is_last_line_of_defense(self):
        # Si la validación de la API se saltara (p. ej. dos peticiones a la vez),
        # el UNIQUE de la BD responde 409 en lugar de un 500.
        with patch("app.routes.usuarios._validar_unicos"):
            response = self.client.post("/api/v1/usuarios", json={**USUARIO, "email": "ana@example.com"})
        self.assertEqual(response.status_code, 409)

    def test_unexpected_errors_do_not_leak_details(self):
        with patch("app.routes.activos._obtener_o_404", side_effect=RuntimeError("secreto")), \
                self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.get("/api/v1/activos/1")
        self.assertEqual((response.status_code, response.json), (500, {"error": "Error interno del servidor."}))

    def test_concurrency_conflicts_are_409_not_503(self):
        from sqlalchemy.exc import OperationalError

        for codigo in (1020, 1205, 1213):
            error = OperationalError("UPDATE activos ...", {}, Exception(codigo, "conflicto"))
            with self.subTest(codigo=codigo), \
                    patch("app.routes.activos._obtener_o_404", side_effect=error), \
                    self.assertLogs(self.app.logger, level="WARNING"):
                response = self.client.patch("/api/v1/activos/1", json={"marca": "X"})
                self.assertEqual(response.status_code, 409)
        caida = OperationalError("SELECT 1", {}, Exception(2003, "Can't connect"))
        with patch("app.routes.activos._obtener_o_404", side_effect=caida), \
                self.assertLogs(self.app.logger, level="ERROR"):
            self.assertEqual(self.client.get("/api/v1/activos/1").status_code, 503)

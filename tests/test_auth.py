from unittest.mock import patch

from itsdangerous import TimestampSigner

from app.auth import emitir_token
from app.extensions import db
from app.models import Usuario
from tests.test_prestamos import APITestCase


class AuthTests(APITestCase):
    def register(self, **changes):
        data = {
            "nombre_completo": "Nuevo",
            "documento": "002",
            "email": "nuevo@example.com",
            "tipo_usuario": "estudiante",
            "password": "  Clave segura 123  ",
        }
        data.update(changes)
        return self.client.post("/api/v1/auth/register", json=data)

    def test_registration_login_and_me(self):
        self.assertEqual(self.loan().status_code, 201)
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password_hash", response.json)
        user = db.session.get(Usuario, response.json["id"])
        self.assertNotEqual(user.password_hash, "  Clave segura 123  ")
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": "nuevo@example.com", "password": "  Clave segura 123  "},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["expires_in"], 3600)
        self.client.environ_base["HTTP_AUTHORIZATION"] = (
            "Bearer " + login.json["access_token"]
        )
        self.assertEqual(self.client.get("/api/v1/auth/me").json["id"], user.id)
        self.assertEqual(self.client.get("/api/v1/usuarios").json["meta"]["total"], 1)
        self.assertEqual(
            self.client.patch("/api/v1/usuarios/1", json={"activo": False}).status_code,
            403,
        )
        self.assertEqual(self.client.post("/api/v1/activos", json={}).status_code, 403)
        self.assertEqual(self.loan(usuario_id=1).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/prestamos/1").status_code, 403)
        self.assertEqual(
            self.client.post("/api/v1/prestamos/1/devolucion", json={}).status_code, 403
        )
        self.assertEqual(self.client.get("/api/v1/prestamos").json["meta"]["total"], 0)

    def test_duplicate_and_privileged_fields(self):
        self.assertEqual(self.register(email="ana@example.com").status_code, 409)
        for field in ("activo", "password_hash", "rol", "id"):
            with self.subTest(field=field):
                self.assertEqual(self.register(**{field: True}).status_code, 400)
        self.assertEqual(self.register(password="short").status_code, 400)

    def test_generic_bad_credentials(self):
        for email in ("ana@example.com", "missing@example.com"):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "Contraseña incorrecta"},
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json, {"error": "Credenciales inválidas."})

    def test_invalid_missing_expired_and_revoked_tokens(self):
        for header in ("", "Basic aaa", "Bearer invalid", "Bearer", "Bearer a b"):
            self.assertEqual(
                self.client.get(
                    "/api/v1/auth/me", headers={"Authorization": header}
                ).status_code,
                401,
            )
        with patch.object(TimestampSigner, "get_timestamp", return_value=1):
            expired = emitir_token(db.session.get(Usuario, 1))
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer " + expired}
            ).status_code,
            401,
        )
        db.session.get(Usuario, 1).activo = False
        db.session.commit()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_changed_password_revokes_token_and_legacy_setup(self):
        user = db.session.get(Usuario, 1)
        user.set_password("Nueva contraseña 123")
        db.session.commit()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        result = self.app.test_cli_runner().invoke(
            args=["set-password", "1"],
            input="Otra contraseña 456\nOtra contraseña 456\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(user.check_password("Otra contraseña 456"))

    def test_missing_secret_fails_closed(self):
        self.app.config["SECRET_KEY"] = None
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 503)

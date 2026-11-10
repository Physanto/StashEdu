from datetime import datetime, timedelta, timezone

import jwt

from app.auth import emitir_token
from app.extensions import db
from app.models import Usuario
from tests.test_prestamos import PASSWORD_PRUEBAS, APITestCase, TestConfig

CLAVE = TestConfig.SECRET_KEY


class RegisterTests(APITestCase):
    def register(self, **changes):
        body = {"usuario_id": 1, "password": "Clave segura 123", "rol_id": 2}
        body.update(changes)
        return self.client.post("/api/v1/auth/register", json=body)

    def test_register_existing_user(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["id"], 1)
        self.assertEqual(response.json["rol"], "operador")
        self.assertNotIn("password_hash", response.json)
        self.assertNotIn("password", response.json)
        ana = db.session.get(Usuario, 1)
        self.assertNotEqual(ana.password_hash, "Clave segura 123")
        self.assertTrue(ana.check_password("Clave segura 123"))

    def test_register_errors(self):
        self.assertEqual(self.register(usuario_id=99).status_code, 404)
        self.assertEqual(self.register(rol_id=99).status_code, 400)
        self.assertEqual(self.register(password="corta").status_code, 400)
        for field in ("usuario_id", "password", "rol_id"):
            with self.subTest(missing=field):
                body = {"usuario_id": 1, "password": "Clave segura 123", "rol_id": 2}
                del body[field]
                self.assertEqual(self.client.post("/api/v1/auth/register", json=body).status_code, 400)
        for value in ("1", True, 0, 1.5):
            with self.subTest(usuario_id=value):
                self.assertEqual(self.register(usuario_id=value).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/auth/register", data="texto").status_code, 400)
        self.assertIsNone(db.session.get(Usuario, 1).password_hash)

    def test_register_conflicts(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 409)  # ya tiene cuenta
        self.assertEqual(self.register(usuario_id=self.admin.id).status_code, 409)
        db.session.add(Usuario(nombre_completo="Off", documento="003", email="off@example.com",
                               tipo_usuario_id=1, habilitado=False))
        db.session.commit()
        self.assertEqual(self.register(usuario_id=3).status_code, 409)  # deshabilitado

    def test_only_admin_registers(self):
        self.client.environ_base.pop("HTTP_AUTHORIZATION")
        self.assertEqual(self.register().status_code, 401)
        for rol_id in (2, 3):
            with self.subTest(rol_id=rol_id):
                cuenta = self.add_account(f"Cuenta {rol_id}", f"R{rol_id}", f"r{rol_id}@example.com", rol_id)
                self.use_token(cuenta)
                self.assertEqual(self.register().status_code, 403)
        self.assertIsNone(db.session.get(Usuario, 1).password_hash)


class LoginTests(APITestCase):
    def login(self, email="admin@example.com", password=PASSWORD_PRUEBAS):
        return self.client.post("/api/v1/auth/login", json={"email": email, "password": password})

    def test_login_returns_jwt(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["token_type"], "Bearer")
        self.assertEqual(response.json["expires_in"], 3600)
        self.assertEqual(response.json["usuario"]["rol"], "admin")
        claims = jwt.decode(response.json["access_token"], CLAVE, algorithms=["HS256"])
        self.assertEqual(claims["sub"], str(self.admin.id))
        self.assertEqual(claims["rol"], "admin")
        self.assertEqual(claims["exp"] - claims["iat"], 3600)

        self.client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + response.json["access_token"]
        me = self.client.get("/api/v1/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json["id"], self.admin.id)

    def test_generic_bad_credentials(self):
        # Ana existe pero no tiene cuenta: misma respuesta que un correo inexistente.
        for email, password in (
            ("admin@example.com", "Contraseña incorrecta"),
            ("ana@example.com", PASSWORD_PRUEBAS),
            ("nadie@example.com", PASSWORD_PRUEBAS),
        ):
            with self.subTest(email=email):
                response = self.login(email, password)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json, {"error": "Credenciales inválidas."})
        self.admin.habilitado = False
        db.session.commit()
        self.assertEqual(self.login().status_code, 401)

    def test_login_validation(self):
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email": "admin@example.com"}).status_code, 400)
        self.assertEqual(self.login(email="sin-arroba").status_code, 400)
        self.assertEqual(self.login(password=123).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/auth/login", data="texto").status_code, 400)


class TokenTests(APITestCase):
    def me(self, token):
        return self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    def test_missing_or_malformed_header(self):
        for header in ("", "Basic aaa", "Bearer", "Bearer a b", "Bearer invalido"):
            with self.subTest(header=header):
                response = self.client.get("/api/v1/auth/me", headers={"Authorization": header})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_expired_token(self):
        pasado = datetime.now(timezone.utc) - timedelta(hours=2)
        response = self.me(emitir_token(self.admin, ahora=pasado))
        self.assertEqual(response.status_code, 401)
        self.assertIn("expiró", response.json["error"])

    def test_tampered_and_foreign_tokens(self):
        claims = jwt.decode(emitir_token(self.admin), CLAVE, algorithms=["HS256"])
        otra_clave = "otra-clave-secreta-de-al-menos-32-caracteres"
        for token in (
            jwt.encode(claims, otra_clave, algorithm="HS256"),          # firma ajena
            jwt.encode(claims, None, algorithm="none"),                 # sin firma
            jwt.encode({**claims, "sub": "1"}, otra_clave, algorithm="HS256"),
            jwt.encode({"sub": str(self.admin.id)}, CLAVE, algorithm="HS256"),  # sin exp
            emitir_token(self.admin)[:-2] + "xx",                       # firma alterada
        ):
            with self.subTest(token=token[:20]):
                self.assertEqual(self.me(token).status_code, 401)

    def test_disabled_account_or_new_password_revokes_token(self):
        token = emitir_token(self.admin)
        self.assertEqual(self.me(token).status_code, 200)
        self.admin.set_password("Nueva contraseña 123")
        db.session.commit()
        self.assertEqual(self.me(token).status_code, 401)
        token = emitir_token(self.admin)
        self.admin.habilitado = False
        db.session.commit()
        self.assertEqual(self.me(token).status_code, 401)

    def test_missing_secret_fails_closed(self):
        self.app.config["SECRET_KEY"] = None
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 503)


class CommandTests(APITestCase):
    def test_crear_admin_and_set_password(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(
            args=["crear-admin", "--nombre", "Root", "--documento", "777", "--email", "root@example.com", "--tipo-usuario", "docente"],
            input="Clave del admin 123\nClave del admin 123\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        root = db.session.scalar(db.select(Usuario).filter_by(email="root@example.com"))
        self.assertEqual(root.rol.codigo, "admin")
        self.assertTrue(root.check_password("Clave del admin 123"))

        repetido = runner.invoke(
            args=["crear-admin", "--nombre", "Otro", "--documento", "777", "--email", "otro@example.com", "--tipo-usuario", "docente"],
            input="Clave del admin 123\nClave del admin 123\n",
        )
        self.assertNotEqual(repetido.exit_code, 0)

        result = runner.invoke(args=["set-password", str(root.id)], input="Otra clave 4567\nOtra clave 4567\n")
        self.assertEqual(result.exit_code, 0, result.output)
        db.session.refresh(root)
        self.assertTrue(root.check_password("Otra clave 4567"))
        sin_cuenta = runner.invoke(args=["set-password", "1"], input="Otra clave 4567\nOtra clave 4567\n")
        self.assertNotEqual(sin_cuenta.exit_code, 0)

from app.extensions import db
from app.models import Activo, Prestamo
from tests.test_prestamos import APITestCase

USUARIO_NUEVO = {"nombre_completo": "Nuevo", "documento": "555", "email": "nuevo@example.com", "tipo_usuario_id": 1}
ACTIVO_NUEVO = {"codigo_inventario": "N1", "nombre": "Tablet", "categoria": "tablet"}


class RolePermissionTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.operador = self.add_account("Operador", "901", "op@example.com", rol_id=2)
        self.consulta = self.add_account("Consulta", "902", "consulta@example.com", rol_id=3)

    def test_without_token_everything_but_health_and_login_is_401(self):
        self.client.environ_base.pop("HTTP_AUTHORIZATION")
        for method, url in (
            ("get", "/api/v1/usuarios"), ("get", "/api/v1/activos"), ("get", "/api/v1/prestamos"),
            ("get", "/api/v1/tipos-usuario"), ("get", "/api/v1/roles"), ("get", "/api/v1/auth/me"),
            ("post", "/api/v1/prestamos"), ("delete", "/api/v1/activos/1"),
        ):
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)

    def test_consulta_only_reads(self):
        self.use_token(self.consulta)
        for url in ("/api/v1/usuarios", "/api/v1/usuarios/1", "/api/v1/activos", "/api/v1/prestamos",
                    "/api/v1/usuarios/1/prestamos", "/api/v1/activos/1/prestamos", "/api/v1/roles"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        for method, url, body in (
            ("post", "/api/v1/usuarios", USUARIO_NUEVO),
            ("patch", "/api/v1/usuarios/1", {"telefono": "123"}),
            ("post", "/api/v1/activos", ACTIVO_NUEVO),
            ("put", "/api/v1/activos/1", ACTIVO_NUEVO),
            ("delete", "/api/v1/activos/1", None),
            ("post", "/api/v1/prestamos", {"usuario_id": 1, "activo_id": 1}),
        ):
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(self.client, method)(url, json=body).status_code, 403)
        self.assertEqual(db.session.get(Activo, 1).estado, "disponible")

    def test_operador_creates_and_edits_but_does_not_delete(self):
        self.use_token(self.operador)
        self.assertEqual(self.client.post("/api/v1/usuarios", json=USUARIO_NUEVO).status_code, 201)
        self.assertEqual(self.client.patch("/api/v1/usuarios/1", json={"telefono": "123"}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/activos", json=ACTIVO_NUEVO).status_code, 201)
        self.assertEqual(self.client.patch("/api/v1/activos/1", json={"marca": "Lenovo"}).status_code, 200)
        self.assertEqual(self.client.delete("/api/v1/activos/1").status_code, 403)
        self.assertEqual(self.client.delete("/api/v1/usuarios/1").status_code, 403)
        # Las cuentas de otros operadores o admins solo las edita un admin.
        self.assertEqual(self.client.patch(f"/api/v1/usuarios/{self.admin.id}", json={"habilitado": False}).status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/usuarios/{self.operador.id}", json={"telefono": "1"}).status_code, 200)
        self.assertTrue(self.admin.habilitado)

    def test_admin_can_delete(self):
        self.assertEqual(self.client.delete("/api/v1/activos/1").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/usuarios/1").status_code, 204)
        self.assertEqual(self.client.patch(f"/api/v1/usuarios/{self.operador.id}", json={"habilitado": False}).status_code, 200)

    def test_role_change_applies_without_new_token(self):
        self.use_token(self.operador)
        self.operador.rol_id = 3
        db.session.commit()
        self.assertEqual(self.client.post("/api/v1/activos", json=ACTIVO_NUEVO).status_code, 403)

    def test_loans_record_who_delivers_and_receives(self):
        self.use_token(self.operador)
        prestamo = self.loan()
        self.assertEqual(prestamo.status_code, 201)
        self.assertEqual(prestamo.json["entregado_por"], {"id": self.operador.id, "nombre_completo": "Operador"})
        self.assertIsNone(prestamo.json["recibido_por"])

        self.use_token(self.consulta)
        self.assertEqual(self.client.post("/api/v1/prestamos/1/devolucion").status_code, 403)

        self.use_token(self.admin)
        devolucion = self.client.post("/api/v1/prestamos/1/devolucion")
        self.assertEqual(devolucion.status_code, 200)
        self.assertEqual(devolucion.json["recibido_por"]["id"], self.admin.id)
        registro = db.session.get(Prestamo, 1)
        self.assertEqual((registro.entregado_por, registro.recibido_por), (self.operador.id, self.admin.id))

    def test_roles_catalog(self):
        response = self.client.get("/api/v1/roles")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["codigo"] for r in response.json["data"]], ["admin", "operador", "consulta"])

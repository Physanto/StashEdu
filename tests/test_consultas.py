from datetime import timedelta

from app.extensions import db
from app.models import Prestamo, Usuario
from app.models.mixins import _ahora
from tests.test_prestamos import APITestCase


class QueryTests(APITestCase):
    def setUp(self):
        super().setUp()
        db.session.add(
            Usuario(nombre_completo="Luis", documento="002", email="luis@example.com", tipo_usuario_id=2)
        )
        db.session.commit()
        for codigo in ("A2", "A3", "A4"):
            self.add_asset(codigo)
        self.loan()                           # 1: activo
        self.loan(activo_id=2)                # 2: vencido
        self.loan(activo_id=3, usuario_id=2)  # 3: devuelto a tiempo
        self.loan(activo_id=4, usuario_id=2)  # 4: devuelto con retraso
        self.client.post("/api/v1/prestamos/3/devolucion")
        self.client.post("/api/v1/prestamos/4/devolucion")
        # Se mueven las fechas al pasado para simular cada estado.
        ahora = _ahora()
        self.set_dates(2, ahora - timedelta(days=10), ahora - timedelta(days=3))
        self.set_dates(3, ahora - timedelta(days=40), ahora - timedelta(days=30), ahora - timedelta(days=35))
        self.set_dates(4, ahora - timedelta(days=20), ahora - timedelta(days=15), ahora - timedelta(days=12))

    def set_dates(self, prestamo_id, prestamo, vencimiento, devolucion=None):
        registro = db.session.get(Prestamo, prestamo_id)
        registro.fecha_prestamo = prestamo
        registro.fecha_vencimiento = vencimiento
        registro.fecha_devolucion = devolucion
        db.session.commit()

    def ids(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.json)
        return [p["id"] for p in response.json["data"]]

    def test_filter_by_state(self):
        self.assertEqual(self.ids("/api/v1/prestamos?estado=activo"), [1])
        self.assertEqual(self.ids("/api/v1/prestamos?estado=vencido"), [2])
        self.assertEqual(self.ids("/api/v1/prestamos?estado=devuelto"), [3])
        self.assertEqual(self.ids("/api/v1/prestamos?estado=devuelto_con_retraso"), [4])
        self.assertEqual(self.ids("/api/v1/prestamos?estado=pendiente"), [1, 2])
        self.assertEqual(self.client.get("/api/v1/prestamos?estado=perdido").status_code, 400)

    def test_filter_by_user_asset_and_dates(self):
        self.assertEqual(self.ids("/api/v1/prestamos"), [1, 2, 4, 3])  # más reciente primero
        self.assertEqual(self.ids("/api/v1/prestamos?usuario_id=2"), [4, 3])
        self.assertEqual(self.ids("/api/v1/prestamos?activo_id=1"), [1])
        desde = (_ahora() - timedelta(days=25)).date().isoformat()
        hasta = (_ahora() - timedelta(days=5)).date().isoformat()
        self.assertEqual(self.ids(f"/api/v1/prestamos?desde={desde}&hasta={hasta}"), [2, 4])
        self.assertEqual(self.ids(f"/api/v1/prestamos?usuario_id=2&estado=devuelto&hasta={hasta}"), [3])
        for query in ("desde=25-10-2026", "hasta=hoy", "usuario_id=uno", f"desde={hasta}&hasta={desde}"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(f"/api/v1/prestamos?{query}").status_code, 400)

    def test_history_by_user_and_asset(self):
        self.assertEqual(self.ids("/api/v1/usuarios/2/prestamos"), [4, 3])
        self.assertEqual(self.ids("/api/v1/usuarios/1/prestamos?estado=vencido"), [2])
        self.assertEqual(self.ids("/api/v1/activos/1/prestamos"), [1])
        # Quién tiene ahora el activo 2, aunque su préstamo ya esté vencido.
        self.assertEqual(self.ids("/api/v1/activos/2/prestamos?estado=pendiente"), [2])
        self.assertEqual(self.ids("/api/v1/activos/3/prestamos?estado=pendiente"), [])
        self.assertEqual(self.client.get("/api/v1/usuarios/99/prestamos").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/activos/99/prestamos").status_code, 404)

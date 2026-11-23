"""Fase 4: el contrato OpenAPI describe exactamente la API que existe."""

import re
import unittest

from app import create_app
from app.openapi import build_spec
from app.utils import parametros_de
from tests.test_prestamos import TestConfig

PUBLICAS = {("/api/v1/health", "get"), ("/api/v1/auth/login", "post")}
METODOS = {"get", "post", "put", "patch", "delete"}


def _ruta_openapi(regla):
    return re.sub(r"<(?:(?:int|path|string):)?([^>]+)>", r"{\1}", regla)


class OpenAPITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.spec = response.json

    def operaciones(self):
        for path, item in self.spec["paths"].items():
            for method, operation in item.items():
                if method in METODOS:
                    yield path, method, operation

    def test_every_route_documented_and_nothing_extra(self):
        implementadas = {}
        for rule in self.app.url_map.iter_rules():
            if rule.rule.startswith("/api/v1/"):
                for method in rule.methods - {"HEAD", "OPTIONS"}:
                    implementadas[(_ruta_openapi(rule.rule), method.lower())] = rule.endpoint
        documentadas = {(path, method) for path, method, _ in self.operaciones()}
        self.assertEqual(set(implementadas), documentadas)

        # Los parámetros de consulta documentados son los que la ruta acepta.
        with self.app.test_request_context():
            for (path, method), endpoint in implementadas.items():
                operation = self.spec["paths"][path][method]
                query = sorted(p["name"] for p in operation.get("parameters", []) if p["in"] == "query")
                with self.subTest(path=path, method=method):
                    self.assertEqual(query, sorted(parametros_de(endpoint)))

    def test_references_resolve_and_operation_ids_are_unique(self):
        def visitar(valor):
            if isinstance(valor, dict):
                if "$ref" in valor:
                    destino = self.spec
                    for parte in valor["$ref"][2:].split("/"):
                        destino = destino[parte]
                for item in valor.values():
                    visitar(item)
            elif isinstance(valor, list):
                for item in valor:
                    visitar(item)

        visitar(self.spec)
        ids = [operation["operationId"] for _, _, operation in self.operaciones()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_security_errors_and_bodies(self):
        esquema = self.spec["components"]["securitySchemes"]["BearerAuth"]
        self.assertEqual((esquema["scheme"], esquema["bearerFormat"]), ("bearer", "JWT"))
        for path, method, operation in self.operaciones():
            with self.subTest(path=path, method=method):
                if (path, method) in PUBLICAS:
                    self.assertEqual(operation["security"], [])
                else:
                    self.assertNotIn("security", operation)  # hereda BearerAuth
                    self.assertIn("401", operation["responses"])
                if method != "get" and (path, method) not in PUBLICAS:
                    self.assertIn("403", operation["responses"])
                if "requestBody" in operation:
                    self.assertIn("413", operation["responses"])
                    self.assertIn("415", operation["responses"])
                if method == "delete":
                    self.assertNotIn("content", operation["responses"]["204"])
        # La devolución es la única operación con cuerpo opcional.
        opcionales = [p for p, m, o in self.operaciones() if "requestBody" in o and not o["requestBody"]["required"]]
        self.assertEqual(opcionales, ["/api/v1/prestamos/{prestamo_id}/devolucion"])

    def test_schemas_match_the_rules(self):
        s = self.spec["components"]["schemas"]
        self.assertNotIn("password_hash", s["Usuario"]["properties"])
        self.assertIn("prestado", s["Activo"]["properties"]["estado"]["enum"])
        self.assertNotIn("prestado", s["ActivoCrear"]["properties"]["estado"]["enum"])
        self.assertEqual(s["UsuarioPatch"]["minProperties"], 1)
        for nombre in ("UsuarioCrear", "ActivoCrear", "PrestamoCrear", "Devolucion", "Registro", "Login"):
            self.assertFalse(s[nombre]["additionalProperties"], nombre)
        self.assertEqual(s["Registro"]["properties"]["password"]["minLength"], 12)
        self.assertIn("entregado_por", s["Prestamo"]["properties"])

    def test_swagger_ui_is_served_locally(self):
        response = self.client.get("/docs/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for archivo in ("swagger-ui.css", "swagger-ui-bundle.js"):
            urls = re.findall(r'(?:src|href)=["\']([^"\']*' + re.escape(archivo) + r')["\']', html)
            self.assertTrue(urls, archivo)
            for url in urls:
                self.assertFalse(url.startswith(("http://", "https://", "//")), url)
                if not url.startswith("/"):
                    url = "/docs/" + url
                with self.client.get(url) as asset:
                    self.assertEqual(asset.status_code, 200, url)
        # La configuración de Swagger UI apunta a nuestro contrato.
        config = self.client.get("/docs/swagger-ui-init.js") if "swagger-ui-init" in html else None
        self.assertIn("/openapi.json", html + (config.get_data(as_text=True) if config else ""))

    def test_formal_openapi_validation(self):
        try:
            from openapi_spec_validator import validate
        except ImportError:
            self.skipTest("Instale requirements-dev.txt para validar formalmente el contrato.")
        validate(build_spec())

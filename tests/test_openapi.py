import re
import unittest

from app import create_app
from app.openapi import build_spec
from tests.test_prestamos import TestConfig


class OpenAPITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.spec = self.client.get("/openapi.json").json

    def test_public_spec_and_every_api_route_documented(self):
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)
        self.assertEqual(self.spec["openapi"], "3.0.3")
        implemented = set()
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith("/api/v1/"):
                continue
            path = re.sub(r"<(?:(?:int|path|string):)?([^>]+)>", r"{\1}", rule.rule)
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                implemented.add((path, method.lower()))
        documented = {(path, method) for path, item in self.spec["paths"].items()
                      for method in item if method in {"get", "post", "put", "patch", "delete"}}
        self.assertEqual(implemented, documented)

    def test_all_references_resolve_and_operation_ids_are_unique(self):
        def visit(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    self.assertTrue(value["$ref"].startswith("#/"))
                    target = self.spec
                    for part in value["$ref"][2:].split("/"):
                        target = target[part.replace("~1", "/").replace("~0", "~")]
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(self.spec)
        ids = [operation["operationId"] for item in self.spec["paths"].values() for operation in item.values()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_security_bodies_statuses_and_pagination_contract(self):
        security = self.spec["components"]["securitySchemes"]["BearerAuth"]
        self.assertEqual(security["scheme"], "bearer")
        self.assertNotIn("bearerFormat", security)
        for path in ("/api/v1/health", "/api/v1/auth/register", "/api/v1/auth/login"):
            for operation in self.spec["paths"][path].values():
                self.assertEqual(operation["security"], [])
        for path, item in self.spec["paths"].items():
            for method, operation in item.items():
                if path not in ("/api/v1/health", "/api/v1/auth/register", "/api/v1/auth/login"):
                    self.assertIn("401", operation["responses"])
                if method in ("post", "put", "patch"):
                    self.assertTrue(operation["requestBody"]["required"])
                    self.assertIn("413", operation["responses"])
                    self.assertIn("415", operation["responses"])
                if method == "delete":
                    self.assertNotIn("content", operation["responses"]["204"])
        for path in ("usuarios", "activos", "prestamos"):
            parameters = self.spec["paths"][f"/api/v1/{path}"]["get"]["parameters"]
            self.assertEqual([parameter["name"] for parameter in parameters], ["page", "per_page"])
            self.assertEqual(parameters[1]["schema"]["maximum"], 100)
        components = self.spec["components"]["schemas"]
        self.assertIn("prestado", components["Activo"]["properties"]["estado"]["enum"])
        self.assertNotIn("prestado", components["ActivoCreate"]["properties"]["estado"]["enum"])
        self.assertEqual(components["Devolucion"]["maxProperties"], 0)
        self.assertFalse(components["Devolucion"]["additionalProperties"])
        self.assertEqual(components["UsuarioPatch"]["minProperties"], 1)
        for model in ("Usuario", "Activo", "Prestamo"):
            self.assertIn("created_at", components[model]["properties"])
            self.assertIn("updated_at", components[model]["properties"])
        self.assertNotIn("password_hash", components["Usuario"]["properties"])

    def test_swagger_ui_bundles_static_assets(self):
        response = self.client.get("/docs/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("/openapi.json", html)
        for asset in ("swagger-ui.css", "swagger-ui-bundle.js", "swagger-ui-standalone-preset.js"):
            urls = re.findall(r'(?:src|href)=["\']([^"\']*' + re.escape(asset) + r')["\']', html)
            self.assertTrue(urls, asset)
            for url in urls:
                self.assertFalse(url.startswith(("https://", "http://", "//")))
                if not url.startswith("/"):
                    url = "/docs/" + url
                with self.client.get(url) as asset_response:
                    self.assertEqual(asset_response.status_code, 200, url)

    def test_formal_openapi_validation(self):
        try:
            from openapi_spec_validator import validate
        except ImportError:
            self.skipTest("Instalar requirements-dev.txt para validar formalmente OpenAPI 3.0.3.")
        validate(build_spec())

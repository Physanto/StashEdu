import unittest

from app.errors import ErrorAPI
from app.models import Usuario
from app.security import hash_password, verificar_password
from tests.test_prestamos import APITestCase


class PasswordTests(unittest.TestCase):
    def test_salted_hash_and_verification(self):
        password = "  Una contraseña segura  "
        first = hash_password(password)
        second = hash_password(password)
        self.assertTrue(first.startswith("scrypt:32768:8:1$"))
        self.assertNotEqual(first, second)
        self.assertNotIn(password, first)
        self.assertTrue(verificar_password(first, password))
        self.assertFalse(verificar_password(first, password.strip()))
        self.assertFalse(verificar_password(first, "Otra contraseña"))
        self.assertFalse(verificar_password(None, password))

    def test_invalid_passwords(self):
        for value in [None, {}, [], True, 123, "short", " " * 12, "a" * 129]:
            with self.subTest(value=type(value).__name__), self.assertRaises(ErrorAPI):
                hash_password(value)


class PasswordPersistenceTests(APITestCase):
    def test_hash_never_serialized(self):
        from app.extensions import db

        user = db.session.get(Usuario, 1)
        self.assertNotIn("password_hash", user.to_dict())
        user.set_password("Una contraseña segura")
        db.session.commit()
        self.assertTrue(user.check_password("Una contraseña segura"))
        self.assertNotIn("password_hash", user.to_dict())
        self.assertNotIn("password", user.to_dict())

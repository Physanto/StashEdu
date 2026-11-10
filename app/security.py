from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import ErrorAPI

PASSWORD_METHOD = "scrypt:32768:8:1"


def validar_password(password):
    # La contraseña se conserva exactamente: no recortar ni normalizar espacios.
    if not isinstance(password, str) or not 12 <= len(password) <= 128 or not password.strip():
        raise ErrorAPI("La contraseña debe ser texto no vacío de entre 12 y 128 caracteres.")
    return password


def hash_password(password):
    return generate_password_hash(validar_password(password), method=PASSWORD_METHOD, salt_length=16)


def verificar_password(password_hash, password):
    return bool(password_hash) and check_password_hash(password_hash, password)

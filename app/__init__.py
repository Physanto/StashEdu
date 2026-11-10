from flask import Flask

from app.errors import registrar_errores
from app.extensions import db, migrate
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config.get("AUTH_TOKEN_MAX_AGE", 3600) <= 0:
        raise ValueError("AUTH_TOKEN_MAX_AGE debe ser positivo.")
    app.json.sort_keys = False  # respeta el orden de los campos en el JSON

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401  (registra los modelos para las migraciones)
    from app.commands import crear_admin, set_password
    from app.routes import (
        activos_bp,
        auth_bp,
        catalogos_bp,
        health_bp,
        prestamos_bp,
        usuarios_bp,
    )

    app.register_blueprint(health_bp)
    app.register_blueprint(catalogos_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(activos_bp)
    app.register_blueprint(prestamos_bp)
    app.register_blueprint(auth_bp)
    app.cli.add_command(crear_admin)
    app.cli.add_command(set_password)
    registrar_errores(app)

    return app

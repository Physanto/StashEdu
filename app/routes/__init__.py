from app.routes.activos import activos_bp
from app.routes.health import health_bp
from app.routes.usuarios import usuarios_bp
from app.routes.prestamos import prestamos_bp
from app.routes.auth import auth_bp

__all__ = ["activos_bp", "health_bp", "usuarios_bp", "prestamos_bp", "auth_bp"]

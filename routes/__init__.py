from .auth import auth_bp
from .main import main_bp
from .perfil import perfil_bp
from .psicologos import psicologos_bp
from .ativacao import ativacao_bp
from .admin import admin_bp


def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(psicologos_bp)
    app.register_blueprint(ativacao_bp)
    app.register_blueprint(admin_bp)

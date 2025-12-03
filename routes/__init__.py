from .auth import auth_bp, init_oauth
from .main import main_bp
from .perfil import perfil_bp
from .psicologos import psicologos_bp
from .ativacao import ativacao_bp
from .admin import admin_bp
from .ferramentas import ferramentas_bp
from routes.notificacoes import notificacoes_bp


def register_routes(app, oauth=None):
    # passa o oauth para o módulo auth
    if oauth is not None:
        init_oauth(oauth)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(psicologos_bp)
    app.register_blueprint(ativacao_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ferramentas_bp)
    app.register_blueprint(notificacoes_bp)

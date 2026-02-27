from flask import Flask, session
from datetime import datetime
from authlib.integrations.flask_client import OAuth
from routes import register_routes
import os
from db.db import get_db_connection
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from utils.logger import app_logger, error_logger

# Carrega variáveis do .env
load_dotenv()

app = Flask(__name__)

# SECRET_KEY obrigatória (não aceita fallback inseguro)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    raise ValueError("SECRET_KEY não configurada! Execute generate_keys.py e configure o .env")

# Configuração de cookies seguros
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas

# Configura CORS (apenas para produção com domínio específico)
if os.environ.get('FLASK_ENV') == 'production':
    CORS(app, origins=[os.environ.get('ALLOWED_ORIGIN', 'https://seudominio.com')], supports_credentials=True)
else:
    # Desenvolvimento: permite localhost
    CORS(app, origins=['http://localhost:5000', 'http://127.0.0.1:5000'], supports_credentials=True)

# Configura Rate Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --------- CONFIG GOOGLE OAUTH (AUTHLIB) ----------
oauth = OAuth(app)

CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth.register(
    name="google",
    server_metadata_url=CONF_URL,
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid email profile"
    },
)
# --------------------------------------------------


@app.context_processor
def inject_now():
    return {'now': datetime.now}


@app.context_processor
def inject_notif_count():
    """
    Injeta 'notif_count' em todos os templates.
    Conta notificações pendentes na tabela notificacoes_agenda
    para o user logado (psicólogo).
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return {'notif_count': 0}

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM notificacoes_agenda
            WHERE user_id = %s AND status = 'pendente'
        """, (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        total = row['total'] if row else 0
        return {'notif_count': total}
    except Exception as e:
        error_logger.error(f"Erro ao contar notificações pendentes: {e}")
        return {'notif_count': 0}


# passa o oauth e limiter para as rotas
register_routes(app, oauth, limiter)


if __name__ == '__main__':
    # Debug apenas em desenvolvimento
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode)

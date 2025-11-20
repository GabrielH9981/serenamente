# app.py
from flask import Flask
from datetime import datetime
from authlib.integrations.flask_client import OAuth
from routes import register_routes
import os

app = Flask(__name__)

# ideal: pegar do ambiente em produção
app.secret_key = os.environ.get('SECRET_KEY', 'e_o_pi_ja_qui_nho')

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


# passa o oauth para as rotas
register_routes(app, oauth)


if __name__ == '__main__':
    app.run(debug=True)

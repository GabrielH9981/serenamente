# app.py
from flask import Flask
from routes import register_routes
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'e_o_pi_ja_qui_nho'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.context_processor
def inject_now():
    return {'now': datetime.now}


register_routes(app)

if __name__ == '__main__':
    app.run(debug=True)

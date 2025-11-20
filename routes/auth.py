# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from db.db import get_db_connection
import secrets  # <-- novo

auth_bp = Blueprint('auth', __name__)

# vai receber o oauth vindo do app.py
oauth = None

def init_oauth(oauth_obj):
    global oauth
    oauth = oauth_obj

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user['password_hash'], senha):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('main.dashboard'))
        else:
            return render_template('login.html', error='Credenciais inválidas')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return render_template('index.html')

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        crp = request.form['crp']
        cpf = request.form['cpf']
        whatsapp = request.form['whatsapp']
        senha = generate_password_hash(request.form['senha'])

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s OR cpf = %s", (email, cpf))
                existing_user = cursor.fetchone()
                cursor.fetchall()

            if existing_user:
                return render_template('register.html', error='E-mail ou CPF já cadastrado.')

            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, crp, cpf, whatsapp_number, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, 0)
                """, (name, email, senha, crp, cpf, whatsapp))
                conn.commit()

            return redirect(url_for('auth.login'))

        except Exception as err:
            print(f"Erro no MySQL: {err}")
            return render_template('register.html', error='Erro ao cadastrar. Tente novamente mais tarde.')

        finally:
            if conn.is_connected():
                conn.close()

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@auth_bp.route('/login/google')
def login_google():
    # nome completo do endpoint do callback dentro do blueprint 'auth'
    redirect_uri = url_for('auth.auth_google_callback', _external=True)
    print("REDIRECT URI GERADO:", redirect_uri)  # <-- adiciona isso
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/google/callback')
def auth_google_callback():
    if oauth is None:
        # Só por segurança, se algo não tiver sido inicializado
        return redirect(url_for('auth.login'))

    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        return render_template('login.html', error='Erro ao autenticar com o Google.')

    email = user_info.get("email")
    name = user_info.get("name")

    if not email:
        return render_template('login.html', error='Não foi possível obter o e-mail da conta Google.')

    # Conecta no banco
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verifica se já existe usuário com esse email
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            # Cria um usuário novo com senha aleatória (não será usada no login normal)
            senha_fake = generate_password_hash(secrets.token_hex(16))

            cursor.execute("""
                INSERT INTO users (name, email, password_hash, crp, cpf, whatsapp_number, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, 0)
            """, (name, email, senha_fake, '', '', ''))
            conn.commit()

            # pega o usuário recém criado
            user_id = cursor.lastrowid
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()

        # Faz login "manual" igual sua rota /login
        session['user_id'] = user['id']
        session['user_name'] = user['name']

        return redirect(url_for('main.dashboard'))

    except Exception as e:
        print(f"Erro no login com Google: {e}")
        return render_template('login.html', error='Erro ao fazer login com Google.')

    finally:
        cursor.close()
        conn.close()


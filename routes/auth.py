# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from db.db import get_db_connection
import secrets  # <-- novo
from utils.validators import validar_cpf
import random
import datetime
from utils.email_utils import send_verification_email


auth_bp = Blueprint('auth', __name__)

# vai receber o oauth vindo do app.py
oauth = None

def init_oauth(oauth_obj):
    global oauth
    oauth = oauth_obj


@auth_bp.before_app_request
def verificar_dados_obrigatorios():
    rotas_livres = {
        'auth.login',
        'auth.register',
        'auth.login_google',
        'auth.auth_google_callback',
        'auth.completar_cadastro',
        'auth.verificar_email',        # ✅ nova
        'auth.enviar_codigo_email',    # ✅ nova
        'ferramentas.conectar_google_calendar',  # ✅ novo
        'ferramentas.google_calendar_callback',  # ✅ novo
        'auth.alterar_email',
        'static'
    }

    endpoint = request.endpoint

    if endpoint in rotas_livres or 'user_id' not in session:
        return

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT crp, cpf, whatsapp_number, email_verified
        FROM users WHERE id = %s
    """, (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return redirect(url_for('auth.login'))

    # 1º: dados obrigatórios de profissional
    if not user.get('crp') or not user.get('cpf') or not user.get('whatsapp_number'):
        return redirect(url_for('auth.completar_cadastro'))

    # 2º: e-mail verificado
    if not user.get('email_verified'):
        return redirect(url_for('auth.verificar_email'))


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

        # ✅ valida CPF
        if not validar_cpf(cpf):
            return render_template(
                'register.html',
                error='CPF inválido.',
                name=name,
                email=email,
                crp=crp,
                cpf=cpf,
                whatsapp=whatsapp
            )

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
        return redirect(url_for('auth.login'))

    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        return render_template('login.html', error='Erro ao autenticar com o Google.')

    email = user_info.get("email")
    name = user_info.get("name")

    if not email:
        return render_template('login.html', error='Não foi possível obter o e-mail da conta Google.')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verifica se já existe usuário com esse email
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            from werkzeug.security import generate_password_hash
            import secrets

            senha_fake = generate_password_hash(secrets.token_hex(16))

            cursor.execute("""
                INSERT INTO users (name, email, password_hash, crp, cpf, whatsapp_number, is_active, email_verified)
                VALUES (%s, %s, %s, %s, %s, %s, 0, 1)
            """, (name, email, senha_fake, '', '', ''))
            conn.commit()

            user_id = cursor.lastrowid
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()

        # seta sessão
        session['user_id'] = user['id']
        session['user_name'] = user['name']

        # se faltar dado obrigatório, manda pra completar cadastro
        if not user.get('crp') or not user.get('cpf') or not user.get('whatsapp_number'):
            return redirect(url_for('auth.completar_cadastro'))

        # se já tiver tudo, vai pro dashboard normal
        return redirect(url_for('main.dashboard'))

    except Exception as e:
        print(f"Erro no login com Google: {e}")
        return render_template('login.html', error='Erro ao fazer login com Google.')

    finally:
        cursor.close()
        conn.close()

@auth_bp.route('/completar-cadastro', methods=['GET', 'POST'])
def completar_cadastro():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            name = request.form.get('name')
            crp = request.form.get('crp')
            cpf = request.form.get('cpf')
            whatsapp = request.form.get('whatsapp')

            # campos obrigatórios
            if not crp or not cpf or not whatsapp:
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
                user = cursor.fetchone()
                return render_template(
                    'completar_cadastro.html',
                    user=user,
                    error='Preencha todos os campos obrigatórios.'
                )

            # ✅ valida CPF
            if not validar_cpf(cpf):
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
                user = cursor.fetchone()
                return render_template(
                    'completar_cadastro.html',
                    user=user,
                    error='CPF inválido.'
                )

            cursor.execute("""
                UPDATE users
                SET name = %s, crp = %s, cpf = %s, whatsapp_number = %s
                WHERE id = %s
            """, (name, crp, cpf, whatsapp, session['user_id']))
            conn.commit()

            session['user_name'] = name
            return redirect(url_for('main.dashboard'))

        # GET: carregar dados atuais do usuário pra preencher o form
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user:
            return redirect(url_for('auth.login'))

        return render_template('completar_cadastro.html', user=user)

    finally:
        cursor.close()
        conn.close()


@auth_bp.route('/enviar-codigo-email')
def enviar_codigo_email():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT email FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user:
            return redirect(url_for('auth.login'))

        email = user['email']

        # gera código de 6 dígitos
        code = f"{random.randint(0, 999999):06d}"
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)

        cursor.execute("""
            UPDATE users
            SET email_verification_code = %s,
                email_verification_expires_at = %s
            WHERE id = %s
        """, (code, expires_at, session['user_id']))
        conn.commit()

    finally:
        cursor.close()
        conn.close()

    # envia e-mail (fora do try/finally pra não segurar conexão à toa)
    send_verification_email(email, code)

    # volta pra tela de verificação (agora com codigo_enviado = True)
    return redirect(url_for('auth.verificar_email'))


@auth_bp.route('/verificar-email', methods=['GET', 'POST'])
def verificar_email():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()

        cursor.execute("""
            SELECT email, email_verification_code, email_verification_expires_at
            FROM users WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()

        codigo_enviado = bool(user and user.get('email_verification_code'))
        email = user['email'] if user else None

        if (not user or
                not user['email_verification_code'] or
                not user['email_verification_expires_at'] or
                codigo != user['email_verification_code'] or
                user['email_verification_expires_at'] < datetime.datetime.utcnow()):
            cursor.close()
            conn.close()
            return render_template(
                'verificar_email.html',
                email=email,
                codigo_enviado=codigo_enviado,
                error='Código inválido ou expirado.'
            )

        # marca como verificado
        cursor.execute("""
            UPDATE users
            SET email_verified = 1,
                email_verification_code = NULL,
                email_verification_expires_at = NULL
            WHERE id = %s
        """, (session['user_id'],))
        conn.commit()

        cursor.close()
        conn.close()
        return redirect(url_for('main.dashboard'))

    # GET: decidir se já existe código ou não
    cursor.execute("""
        SELECT email, email_verification_code
        FROM users WHERE id = %s
    """, (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    email = user['email'] if user else None
    codigo_enviado = bool(user and user.get('email_verification_code'))

    return render_template('verificar_email.html', email=email, codigo_enviado=codigo_enviado)


@auth_bp.route('/alterar-email', methods=['GET', 'POST'])
def alterar_email():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        novo_email = request.form.get('email', '').strip()

        if not novo_email:
            cursor.execute("SELECT email FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return render_template(
                'alterar_email.html',
                email=user['email'] if user else '',
                error='Informe um e-mail válido.'
            )

        # checar se já existe outro usuário com esse e-mail
        cursor.execute(
            "SELECT id FROM users WHERE email = %s AND id <> %s",
            (novo_email, session['user_id'])
        )
        ja_existe = cursor.fetchone()
        if ja_existe:
            cursor.execute("SELECT email FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return render_template(
                'alterar_email.html',
                email=user['email'] if user else '',
                error='Já existe uma conta com esse e-mail.'
            )

        # atualiza email e reseta verificação
        cursor.execute("""
            UPDATE users
            SET email = %s,
                email_verified = 0,
                email_verification_code = NULL,
                email_verification_expires_at = NULL
            WHERE id = %s
        """, (novo_email, session['user_id']))
        conn.commit()

        cursor.close()
        conn.close()

        # depois que alterar, manda pra tela de verificar e-mail (estado "enviar código")
        return redirect(url_for('auth.verificar_email'))

    # GET: mostrar o formulário com o e-mail atual
    cursor.execute("SELECT email FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('alterar_email.html', email=user['email'] if user else '')



from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from PIL import Image
from io import BytesIO
import base64
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'e_o_pi_ja_qui_nho'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.context_processor
def inject_now():
    return {'now': datetime.now}


def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='root',
        database='catalogo_psicologos'
    )


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Credenciais inválidas')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
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

            # 1. Verificar se email ou CPF já estão cadastrados
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s OR cpf = %s", (email, cpf))
                existing_user = cursor.fetchone()
                # Leitura completa, mesmo se None
                cursor.fetchall()

            if existing_user:
                return render_template('register.html', error='E-mail ou CPF já cadastrado.')

            # 2. Inserir novo usuário
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, crp, cpf, whatsapp_number, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, 0)
                """, (name, email, senha, crp, cpf, whatsapp))
                conn.commit()

            return redirect(url_for('login'))

        except mysql.connector.Error as err:
            # Log do erro no terminal (evite exibir erro técnico ao usuário)
            print(f"Erro no MySQL: {err}")
            return render_template('register.html', error='Erro ao cadastrar. Tente novamente mais tarde.')

        finally:
            if conn.is_connected():
                conn.close()

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/parceiro')
def parceiro():
    return render_template('psicologo_apresentacao.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Buscar perfil existente
    cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (session['user_id'],))
    profile = cursor.fetchone()

    if request.method == 'POST':
        # Trata imagem base64 recortada
        cropped_data = request.form.get('cropped_image')
        image_filename = None

        if cropped_data:
            try:
                header, encoded = cropped_data.split(",", 1)
                data = base64.b64decode(encoded)
                img = Image.open(BytesIO(data)).convert("RGB")

                filename = f"profile_{session['user_id']}.jpg"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                img = img.resize((300, 300))
                img.save(save_path, format='JPEG')

                # Salva o caminho relativo ao static/
                image_filename = f"uploads/{filename}"
            except Exception as e:
                print("Erro ao salvar imagem recortada:", e)

        # Dados do formulário
        data = {
            'short_bio': request.form.get('short_bio'),
            'full_bio': request.form.get('full_bio'),
            'profile_picture_url': image_filename or (profile.get('profile_picture_url') if profile else ''),
            'location': request.form.get('location'),
            'price_range': request.form.get('price_range'),
            'atendimento_online': 1 if request.form.get('atendimento_online') else 0,
            'atendimento_presencial': 1 if request.form.get('atendimento_presencial') else 0,
            'whatsapp_number': request.form.get('whatsapp_number'),
            'instagram_url': request.form.get('instagram_url'),
            'website_url': request.form.get('website_url')
        }

        if profile:
            cursor.execute("""
                UPDATE profiles SET short_bio=%s, full_bio=%s, profile_picture_url=%s, location=%s,
                price_range=%s, atendimento_online=%s, atendimento_presencial=%s,
                whatsapp_number=%s, instagram_url=%s, website_url=%s WHERE user_id=%s
            """, (
                data['short_bio'], data['full_bio'], data['profile_picture_url'], data['location'],
                data['price_range'], data['atendimento_online'], data['atendimento_presencial'],
                data['whatsapp_number'], data['instagram_url'], data['website_url'], session['user_id']
            ))
        else:
            cursor.execute("""
                INSERT INTO profiles (
                    user_id, short_bio, full_bio, profile_picture_url, location,
                    price_range, atendimento_online, atendimento_presencial,
                    whatsapp_number, instagram_url, website_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'], data['short_bio'], data['full_bio'], data['profile_picture_url'], data['location'],
                data['price_range'], data['atendimento_online'], data['atendimento_presencial'],
                data['whatsapp_number'], data['instagram_url'], data['website_url']
            ))
            conn.commit()
            cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (session['user_id'],))
            profile = cursor.fetchone()

    profile_id = profile['id'] if profile else None

    # Listas
    cursor.execute("SELECT * FROM approaches")
    approaches = cursor.fetchall()

    cursor.execute("SELECT * FROM experiencias")
    experiencias = cursor.fetchall()

    cursor.execute("SELECT * FROM publicos_alvo")
    publicos = cursor.fetchall()

    # Selecionados
    selected_approaches, selected_experiencias, selected_publicos = [], [], []
    if profile_id:
        cursor.execute("SELECT approach_id FROM profile_approaches WHERE profile_id = %s", (profile_id,))
        selected_approaches = [row['approach_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT experiencia_id FROM profile_experiencias WHERE profile_id = %s", (profile_id,))
        selected_experiencias = [row['experiencia_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT publico_id FROM profile_publicos_alvo WHERE profile_id = %s", (profile_id,))
        selected_publicos = [row['publico_id'] for row in cursor.fetchall()]

    # Atualizar seleções
    if request.method == 'POST' and profile_id:
        # Abordagem (única)
        cursor.execute("DELETE FROM profile_approaches WHERE profile_id = %s", (profile_id,))
        selected_approach_id = request.form.get("approach")
        if selected_approach_id:
            cursor.execute("INSERT INTO profile_approaches (profile_id, approach_id) VALUES (%s, %s)", (profile_id, selected_approach_id))

        # Experiências
        cursor.execute("DELETE FROM profile_experiencias WHERE profile_id = %s", (profile_id,))
        for eid in request.form.getlist("experiencias"):
            cursor.execute("INSERT INTO profile_experiencias (profile_id, experiencia_id) VALUES (%s, %s)", (profile_id, eid))

        # Públicos
        cursor.execute("DELETE FROM profile_publicos_alvo WHERE profile_id = %s", (profile_id,))
        for pid in request.form.getlist("publicos"):
            cursor.execute("INSERT INTO profile_publicos_alvo (profile_id, publico_id) VALUES (%s, %s)", (profile_id, pid))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('perfil'))

    cursor.close()
    conn.close()

    return render_template('perfil.html', profile=profile or {},
                           approaches=approaches,
                           experiencias=experiencias,
                           publicos=publicos,
                           selected_approaches=selected_approaches,
                           selected_experiencias=selected_experiencias,
                           selected_publicos=selected_publicos)


@app.route('/psicologos')
def psicologos_publicos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM approaches")
    abordagens = cursor.fetchall()

    cursor.execute("SELECT * FROM experiencias")
    experiencias = cursor.fetchall()

    cursor.execute("SELECT * FROM publicos_alvo")
    publicos = cursor.fetchall()

    query = """
        SELECT p.*, u.name FROM profiles p
        JOIN users u ON p.user_id = u.id
        WHERE u.is_active = 1
    """
    params = []

    nome = request.args.get('nome')
    if nome:
        query += " AND u.name LIKE %s"
        params.append(f"%{nome}%")

    modalidade = request.args.get('modalidade')
    if modalidade == 'online':
        query += " AND p.atendimento_online = 1"
    elif modalidade == 'presencial':
        query += " AND p.atendimento_presencial = 1"

    valor = request.args.get('valor')
    if valor and '-' in valor:
        min_v, max_v = valor.split('-')
        query += " AND CAST(SUBSTRING_INDEX(p.price_range, '-', 1) AS UNSIGNED) >= %s AND CAST(SUBSTRING_INDEX(p.price_range, '-', -1) AS UNSIGNED) <= %s"
        params.extend([min_v, max_v])

    approach_id = request.args.get('approach')
    if approach_id:
        query += " AND p.id IN (SELECT profile_id FROM profile_approaches WHERE approach_id = %s)"
        params.append(approach_id)

    experiencia_id = request.args.get('experiencia')
    if experiencia_id:
        query += " AND p.id IN (SELECT profile_id FROM profile_experiencias WHERE experiencia_id = %s)"
        params.append(experiencia_id)

    publico_id = request.args.get('publico')
    if publico_id:
        query += " AND p.id IN (SELECT profile_id FROM profile_publicos_alvo WHERE publico_id = %s)"
        params.append(publico_id)

    cursor.execute(query, params)
    perfis = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("publicos.html",
                           perfis=perfis,
                           abordagens=abordagens,
                           experiencias=experiencias,
                           publicos=publicos)


@app.route('/psicologo/<int:profile_id>')
def perfil_publico(profile_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Buscar perfil e nome
    cursor.execute("""
        SELECT p.*, u.name, u.crp
        FROM profiles p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (profile_id,))
    profile = cursor.fetchone()

    if not profile:
        cursor.close()
        conn.close()
        return "Perfil não encontrado", 404

    # Buscar abordagens, experiências e públicos
    cursor.execute("""
        SELECT a.* FROM approaches a
        JOIN profile_approaches pa ON pa.approach_id = a.id
        WHERE pa.profile_id = %s
    """, (profile_id,))
    abordagens = cursor.fetchall()

    cursor.execute("""
        SELECT e.* FROM experiencias e
        JOIN profile_experiencias pe ON pe.experiencia_id = e.id
        WHERE pe.profile_id = %s
    """, (profile_id,))
    experiencias = cursor.fetchall()

    cursor.execute("""
        SELECT p.* FROM publicos_alvo p
        JOIN profile_publicos_alvo pp ON pp.publico_id = p.id
        WHERE pp.profile_id = %s
    """, (profile_id,))
    publicos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("perfil_publico.html",
                           profile=profile,
                           abordagens=abordagens,
                           experiencias=experiencias,
                           publicos=publicos)


# rota para ativar conta com código enviado via whatsapp
@app.route('/ativar', methods=['GET', 'POST'])
def ativar_conta():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        codigo = request.form.get('codigo')
        user_id_logado = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verifica se o código pertence ao usuário logado, não usado ainda, e o usuário está inativo
        cursor.execute("""
            SELECT ac.user_id, ac.plan_duration_days FROM activation_codes ac
            JOIN users u ON ac.user_id = u.id
            WHERE ac.code = %s AND ac.user_id = %s AND u.is_active = 0 AND ac.activated_at IS NULL
        """, (codigo, user_id_logado))
        result = cursor.fetchone()

        if result:
            now = datetime.now()

            # Ativa a conta e registra o momento da ativação
            cursor.execute("UPDATE users SET is_active = 1 WHERE id = %s", (user_id_logado,))
            cursor.execute("UPDATE activation_codes SET activated_at = %s, used = 1 WHERE code = %s", (now, codigo))
            conn.commit()
            cursor.close()
            conn.close()

            return """
            <script>
                alert("Conta ativada com sucesso!");
                window.location.href = "/";
            </script>
            """
        else:
            cursor.close()
            conn.close()
            return """
            <script>
                alert("Código inválido, expirado ou não pertence à sua conta.");
                window.location.href = "/ativar";
            </script>
            """

    return render_template("ativar.html")


if __name__ == '__main__':
    app.run(debug=True)

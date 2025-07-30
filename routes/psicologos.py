# routes/psicologos.py
from flask import Blueprint, render_template, request
from db.db import get_db_connection
import datetime

psicologos_bp = Blueprint('psicologos', __name__)


@psicologos_bp.route('/psicologos')
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


from flask import request

@psicologos_bp.route('/psicologo/<int:profile_id>')
def perfil_publico(profile_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    viewer_ip = request.remote_addr

    # Verifica se já há visualização desse IP para esse perfil nas últimas 24h
    cursor.execute("""
            SELECT viewed_at FROM profile_views
            WHERE profile_id = %s AND viewer_ip = %s
            ORDER BY viewed_at DESC
            LIMIT 1
        """, (profile_id, viewer_ip))

    last_view = cursor.fetchone()
    now = datetime.datetime.utcnow()

    if not last_view or (now - last_view['viewed_at']) > datetime.timedelta(hours=24):
        cursor.execute("""
                INSERT INTO profile_views (profile_id, viewer_ip)
                VALUES (%s, %s)
            """, (profile_id, viewer_ip))
        conn.commit()

    # Consulta dos dados do perfil (como já está na sua rota)
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
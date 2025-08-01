# routes/psicologos.py
from flask import Blueprint, render_template, request, session
from db.db import get_db_connection
from datetime import datetime, timedelta
import math
import random

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

    # Filtros
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

    # Página e offset
    page = int(request.args.get('page', 1))
    per_page = 12
    offset = (page - 1) * per_page

    # Executa consulta
    cursor.execute(query, params)
    all_profiles = cursor.fetchall()
    total = len(all_profiles)

    # Se não houver perfis, evita erro
    if total == 0:
        perfis_paginados = []
        total_pages = 1
    else:
        # Gera uma chave de sessão com base nos filtros atuais
        filtro_chave = f"{nome}_{modalidade}_{valor}_{approach_id}_{experiencia_id}_{publico_id}"
        filtro_chave = filtro_chave.replace('None', '').replace(' ', '_')

        session_key = f"perfil_ordem_{filtro_chave}"

        if session_key not in session:
            print("gerando nova ordem aleatória para sessão:", session_key)
            id_list = [p['id'] for p in all_profiles]
            random.shuffle(id_list)
            session[session_key] = id_list
        else:
            print("usando ordem já existente da sessão:", session_key)
            id_list = session[session_key]

        # Ordena os perfis conforme a lista salva na sessão
        id_to_profile = {p['id']: p for p in all_profiles}
        ordered_profiles = [id_to_profile[i] for i in id_list if i in id_to_profile]

        perfis_paginados = ordered_profiles[offset:offset + per_page]
        total_pages = math.ceil(total / per_page)

    cursor.close()
    conn.close()

    return render_template("publicos.html",
                           perfis=perfis_paginados,
                           abordagens=abordagens,
                           experiencias=experiencias,
                           publicos=publicos,
                           current_page=page,
                           total_pages=total_pages)


@psicologos_bp.route('/psicologo/<int:profile_id>')
def perfil_publico(profile_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- CONTROLE DE VISUALIZAÇÕES COM SESSION ---
    if 'views' not in session:
        session['views'] = {}

    now = datetime.utcnow()
    last_view_str = session['views'].get(str(profile_id))
    should_insert = False

    if not last_view_str:
        should_insert = True
    else:
        try:
            last_view = datetime.strptime(last_view_str, '%Y-%m-%d %H:%M:%S')
            if now - last_view > timedelta(hours=24):
                should_insert = True
        except ValueError:
            should_insert = True  # Em caso de erro na session, registra

    if should_insert:
        viewer_ip = request.remote_addr
        cursor.execute("""
            INSERT INTO profile_views (profile_id, viewer_ip)
            VALUES (%s, %s)
        """, (profile_id, viewer_ip))
        conn.commit()
        session['views'][str(profile_id)] = now.strftime('%Y-%m-%d %H:%M:%S')
        session.modified = True

    # --- CONSULTA DE DADOS DO PERFIL ---
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
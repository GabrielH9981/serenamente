from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db.db import get_db_connection
import secrets, string
from datetime import datetime, timedelta  # ✅ Mantém apenas a classe e função necessárias
import os

admin_bp = Blueprint('admin', __name__)

# Configurações básicas do admin
ADMIN_USER = os.environ.get('ADMIN_USER')
ADMIN_PASS = os.environ.get('ADMIN_PASS')


@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin.painel_admin'))
        else:
            flash('Credenciais inválidas', 'danger')
    return render_template('admin_login.html')


@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/admin', methods=['GET', 'POST'])
def painel_admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    codigo_gerado = None
    desativados = []

    if request.method == 'POST':
        if request.form.get('acao') == 'gerar_codigo':
            user_id = int(request.form['user_id'])
            dias = int(request.form['dias'])

            codigo = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            cursor.execute("""
                INSERT INTO activation_codes (user_id, code, plan_duration_days, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (user_id, codigo, dias))
            conn.commit()
            codigo_gerado = codigo

        elif request.form.get('acao') == 'desativar_expirados':
            hoje = datetime.now()
            cursor.execute("""
                SELECT ac.user_id, ac.activated_at, ac.plan_duration_days
                FROM activation_codes ac
                JOIN users u ON ac.user_id = u.id
                WHERE u.is_active = 1 AND ac.activated_at IS NOT NULL
            """)

            for row in cursor.fetchall():
                expirado = row['activated_at'] + timedelta(days=row['plan_duration_days'])
                if hoje > expirado:
                    desativados.append(row['user_id'])
                    cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s", (row['user_id'],))
            conn.commit()

    # NOVO BLOCO: Visualizações
    periodo = request.args.get('periodo', '7')
    hoje = datetime.utcnow()

    if periodo == '30':
        data_limite = hoje - timedelta(days=30)
    elif periodo == 'all':
        data_limite = None
    else:
        data_limite = hoje - timedelta(days=7)

    if data_limite:
        cursor.execute("""
            SELECT pv.profile_id, COUNT(*) AS total_views, u.name
            FROM profile_views pv
            JOIN profiles p ON pv.profile_id = p.id
            JOIN users u ON p.user_id = u.id
            WHERE pv.viewed_at >= %s
            GROUP BY pv.profile_id
            ORDER BY total_views DESC
            LIMIT 10
        """, (data_limite,))
    else:
        cursor.execute("""
            SELECT pv.profile_id, COUNT(*) AS total_views, u.name
            FROM profile_views pv
            JOIN profiles p ON pv.profile_id = p.id
            JOIN users u ON p.user_id = u.id
            GROUP BY pv.profile_id
            ORDER BY total_views DESC
            LIMIT 10
        """)

    mais_visualizados = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_painel.html',
                           codigo=codigo_gerado,
                           desativados=desativados,
                           mais_visualizados=mais_visualizados,
                           periodo=periodo)

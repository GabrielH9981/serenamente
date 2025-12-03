# routes/notificacoes.py
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from db.db import get_db_connection
from datetime import datetime, timedelta
import re
import requests

from routes.ferramentas import refresh_google_tokens, criar_evento_agenda_for_user

notificacoes_bp = Blueprint('notificacoes', __name__)


@notificacoes_bp.route('/notificacoes')
def listar_notificacoes():
    """Lista notificações de agendamento do psicólogo logado (apenas pendentes)."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            n.*,
            p.id AS profile_id,
            p.scheduling_mode,
            u.name AS psicologo_nome
        FROM notificacoes_agenda n
        JOIN profiles p ON n.profile_id = p.id
        JOIN users u   ON n.user_id   = u.id
        WHERE n.user_id = %s
          AND n.status = 'pendente'
        ORDER BY n.created_at DESC
    """, (session['user_id'],))

    notificacoes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('notificacoes.html', notificacoes=notificacoes)


@notificacoes_bp.route('/notificacoes/criar', methods=['POST'])
def criar_notificacao():
    """
    Chamado pelo perfil público quando o paciente clica em Agendar/Enviar pedido.
    Espera JSON: { nome, telefone, date, time, profile_id }
    """
    data = request.get_json() or {}
    print("📩 Payload recebido em /notificacoes/criar:", data)

    nome = (data.get('nome') or '').strip()
    telefone = (data.get('telefone') or '').strip()
    date_str = data.get('date')
    time_str = data.get('time')
    profile_id = data.get('profile_id')

    if not (nome and telefone and date_str and time_str and profile_id):
        print("❌ Campos faltando em /notificacoes/criar")
        return jsonify({"success": False, "error": "missing_fields"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Descobre qual usuário (psicólogo) é dono do profile + modo de agendamento
    cursor.execute("""
        SELECT user_id, scheduling_mode
        FROM profiles
        WHERE id = %s
    """, (profile_id,))
    prof = cursor.fetchone()

    if not prof:
        cursor.close()
        conn.close()
        print("❌ Profile não encontrado em /notificacoes/criar")
        return jsonify({"success": False, "error": "profile_not_found"}), 404

    psic_user_id = prof['user_id']
    scheduling_mode = prof.get('scheduling_mode') or 'manual'
    if scheduling_mode not in ('none', 'manual', 'auto'):
        scheduling_mode = 'manual'

    # Cria notificação pendente
    cursor.execute("""
        INSERT INTO notificacoes_agenda
          (profile_id, user_id, paciente_nome, paciente_telefone, data, hora, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'pendente')
    """, (profile_id, psic_user_id, nome, telefone, date_str, time_str))

    conn.commit()
    notif_id = cursor.lastrowid
    print(f"✅ Notificação criada (id={notif_id}) para user_id={psic_user_id} (modo={scheduling_mode})")

    # Se o modo for "auto", já cria o evento na Google Agenda
    if scheduling_mode == 'auto':
        titulo = f"Sessão com {nome}"
        descricao = f"Telefone do paciente: {telefone}"
        ok, resp_info = criar_evento_agenda_for_user(
            psic_user_id,
            titulo=titulo,
            data=date_str,
            hora_inicio=time_str,
            hora_fim=None,
            descricao=descricao
        )
        if ok:
            print(f"📅 Evento criado automaticamente na agenda do user_id={psic_user_id} (notif_id={notif_id})")
        else:
            print(f"⚠️ Falha ao criar evento automático (notif_id={notif_id}): {resp_info}")

    cursor.close()
    conn.close()

    return jsonify({"success": True, "id": notif_id})


@notificacoes_bp.route('/notificacoes/acao', methods=['POST'])
def acao_notificacao():
    """
    Ações do psicólogo: AGENDAR SESSÃO, CONVERSAR, CANCELAR.
    Recebe notif_id e acao (agendar|conversar|cancelar) via form.
    """
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    notif_id = request.form.get('notif_id')
    acao = request.form.get('acao')

    if not notif_id or not acao:
        return redirect(url_for('notificacoes.listar_notificacoes'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Puxa notificação + modo de agendamento do perfil
    cursor.execute("""
        SELECT n.*, p.scheduling_mode
        FROM notificacoes_agenda n
        JOIN profiles p ON n.profile_id = p.id
        WHERE n.id = %s AND n.user_id = %s
    """, (notif_id, session['user_id']))
    notif = cursor.fetchone()

    if not notif:
        cursor.close()
        conn.close()
        return redirect(url_for('notificacoes.listar_notificacoes'))

    scheduling_mode = notif.get('scheduling_mode') or 'manual'
    if scheduling_mode not in ('none', 'manual', 'auto'):
        scheduling_mode = 'manual'

    # Normaliza data/hora em string
    data_day = notif['data']
    hora_str = notif['hora']

    if isinstance(data_day, datetime):
        data_day = data_day.date()
    data_str = data_day.isoformat() if hasattr(data_day, 'isoformat') else str(data_day)

    if isinstance(hora_str, datetime):
        hora_str = hora_str.time()
    time_str = hora_str.strftime('%H:%M') if hasattr(hora_str, 'strftime') else str(hora_str)[:5]

    paciente_nome = notif['paciente_nome']
    paciente_tel = notif['paciente_telefone']

    # --- Ação: CANCELAR ---
    if acao == 'cancelar':
        cursor.execute("""
            UPDATE notificacoes_agenda
            SET status = 'cancelado'
            WHERE id = %s
        """, (notif_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('notificacoes.listar_notificacoes'))

    # --- Ação: CONVERSAR COM O PACIENTE (WhatsApp) ---
    if acao == 'conversar':
        cursor.execute("""
            UPDATE notificacoes_agenda
            SET status = 'conversar'
            WHERE id = %s
        """, (notif_id,))
        conn.commit()
        cursor.close()
        conn.close()

        tel_digits = re.sub(r'\D', '', paciente_tel or '')
        if tel_digits.startswith('55'):
            wa_number = tel_digits
        else:
            wa_number = '55' + tel_digits

        msg = f"Olá, vi sua solicitação de agendamento para {data_str} às {time_str}."
        wa_link = f"https://wa.me/{wa_number}?text={requests.utils.requote_uri(msg)}"
        return redirect(wa_link)

    # --- Ação: AGENDAR SESSÃO (criar evento na Google Agenda) ---
    if acao == 'agendar':
        # Se o modo é AUTO, teoricamente já foi criado na hora que a notificação nasceu.
        if scheduling_mode == 'auto':
            print(f"ℹ️ Ação 'agendar' ignorada (modo=auto, notif_id={notif_id})")
            cursor.execute("""
                UPDATE notificacoes_agenda
                SET status = 'agendado'
                WHERE id = %s
            """, (notif_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('notificacoes.listar_notificacoes'))

        # pega access token do Google do psicólogo
        cursor.execute("""
            SELECT google_cal_access_token
            FROM users
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
        access_token = user['google_cal_access_token'] if user else None

        if not access_token:
            # sem agenda conectada → só marca como "agendado" e segue
            cursor.execute("""
                UPDATE notificacoes_agenda
                SET status = 'agendado'
                WHERE id = %s
            """, (notif_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('notificacoes.listar_notificacoes'))

        # monta evento
        try:
            import datetime as dtmod

            start_dt = dtmod.datetime.fromisoformat(f"{data_str}T{time_str}:00")
            end_dt = start_dt + dtmod.timedelta(minutes=50)
            start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
            end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            body = {
                "summary": f"Sessão com {paciente_nome}",
                "description": f"Telefone do paciente: {paciente_tel}",
                "start": {"dateTime": start_iso, "timeZone": "America/Sao_Paulo"},
                "end": {"dateTime": end_iso, "timeZone": "America/Sao_Paulo"}
            }

            resp = requests.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers=headers,
                json=body,
                timeout=10
            )

            # se token expirou, tenta refresh
            if resp.status_code == 401:
                print("notificacoes/acao: 401 ao criar evento, tentando refresh...")
                refreshed = refresh_google_tokens(session['user_id'])
                if refreshed and refreshed.get('access_token'):
                    headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                    resp = requests.post(
                        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                        headers=headers,
                        json=body,
                        timeout=10
                    )

            if resp.status_code >= 400:
                print("Erro criando evento via notificação:", resp.status_code, resp.text)

            resp.raise_for_status()

            # se deu certo, marca notificacao como agendada
            cursor.execute("""
                UPDATE notificacoes_agenda
                SET status = 'agendado'
                WHERE id = %s
            """, (notif_id,))
            conn.commit()

        except Exception as e:
            print("Erro ao criar evento via notificacao:", e)

        cursor.close()
        conn.close()
        return redirect(url_for('notificacoes.listar_notificacoes'))

    # fallback
    cursor.close()
    conn.close()
    return redirect(url_for('notificacoes.listar_notificacoes'))


@notificacoes_bp.route('/notificacoes/limpar', methods=['POST'])
def limpar_todas_notificacoes():
    """
    Marca todas as notificações pendentes do psicólogo logado como 'cancelado'.
    Usado pelo botão 'Limpar todas'.
    """
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE notificacoes_agenda
            SET status = 'cancelado'
            WHERE user_id = %s AND status = 'pendente'
        """, (session['user_id'],))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('notificacoes.listar_notificacoes'))


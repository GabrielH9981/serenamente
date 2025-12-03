# routes/ferramentas.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from db.db import get_db_connection
from . import auth as auth_routes  # importa o módulo auth (com oauth)
from urllib.parse import quote_plus
import calendar
import datetime
import requests
import os

ferramentas_bp = Blueprint('ferramentas', __name__)

# constants / env
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


def refresh_google_tokens(user_id):
    """
    Usa refresh_token salvo no banco para obter novo access_token.
    Atualiza google_cal_access_token, google_cal_refresh_token (se vier novo)
    e google_cal_token_expiry no banco.
    Retorna dict com 'access_token' e 'expires_at' em caso de sucesso, ou None.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT google_cal_refresh_token
            FROM users WHERE id = %s
        """, (user_id,))
        row = cursor.fetchone()
        if not row or not row.get('google_cal_refresh_token'):
            print("refresh_google_tokens: sem refresh_token no banco")
            return None

        refresh_token = row['google_cal_refresh_token']

        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=10)
        if resp.status_code != 200:
            # tenta detectar invalid_grant para limpar tokens no DB
            print("Refresh token failed:", resp.status_code, resp.text)
            try:
                err = resp.json()
                if err.get('error') == 'invalid_grant':
                    # limpa tokens no banco (refresh revogado)
                    cleanup_conn = get_db_connection()
                    cur = cleanup_conn.cursor()
                    cur.execute("""
                        UPDATE users
                        SET google_cal_access_token=NULL, google_cal_refresh_token=NULL, google_cal_token_expiry=NULL
                        WHERE id=%s
                    """, (user_id,))
                    cleanup_conn.commit()
                    cur.close()
                    cleanup_conn.close()
                    print("refresh_google_tokens: invalid_grant -> tokens limpos no banco")
                    return None
            except Exception:
                pass

            return None

        token_data = resp.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")  # segundos
        new_refresh_token = token_data.get("refresh_token")  # pode vir normalmente só na primeira concessão

        if not access_token:
            print("Refresh response sem access_token:", token_data)
            return None

        expiry_dt = None
        if expires_in:
            expiry_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=int(expires_in))

        # atualiza DB: access_token, expiry e se há novo refresh_token, salva
        cur_upd = conn.cursor()
        if new_refresh_token:
            cur_upd.execute("""
                UPDATE users
                SET google_cal_access_token = %s,
                    google_cal_refresh_token = %s,
                    google_cal_token_expiry = %s
                WHERE id = %s
            """, (access_token, new_refresh_token, expiry_dt, user_id))
            print("refresh_google_tokens: novo refresh_token recebido e salvo.")
        else:
            cur_upd.execute("""
                UPDATE users
                SET google_cal_access_token = %s,
                    google_cal_token_expiry = %s
                WHERE id = %s
            """, (access_token, expiry_dt, user_id))
            print("refresh_google_tokens: access_token atualizado, expiry salvo.")
        conn.commit()
        cur_upd.close()

        return {"access_token": access_token, "expires_at": expiry_dt}

    except Exception as e:
        print("Erro ao tentar refresh token:", e)
        return None
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def get_events_from_calendar(access_token, time_min, time_max):
    """
    Faz a requisição à Calendar API e retorna o objeto Response.
    (Essa função não tenta refresh; espere que a chamada que usa ela já tenha feito refresh proativo.)
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 250,
    }
    resp = requests.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers=headers,
        params=params,
        timeout=10
    )
    return resp


@ferramentas_bp.route('/ferramentas')
def ferramentas_home():
    """Página principal da agenda mensal do psicólogo."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # --- LÊ MÊS / ANO DA URL ---
    hoje = datetime.date.today()
    ano = request.args.get("ano", type=int, default=hoje.year)
    mes = request.args.get("mes", type=int, default=hoje.month)

    # Garantir mês entre 1 e 12
    if mes < 1:
        mes = 12
        ano -= 1
    if mes > 12:
        mes = 1
        ano += 1

    # Primeiro e último dia do mês
    first_day = datetime.date(ano, mes, 1)
    last_day_num = calendar.monthrange(ano, mes)[1]

    # Intervalo pro Google Calendar: mês inteiro
    time_min = datetime.datetime.combine(first_day, datetime.time.min).isoformat() + 'Z'

    # primeiro dia do mês seguinte
    if mes == 12:
        next_month_first = datetime.date(ano + 1, 1, 1)
    else:
        next_month_first = datetime.date(ano, mes + 1, 1)

    time_max = datetime.datetime.combine(next_month_first, datetime.time.min).isoformat() + 'Z'

    # Label do mês
    meses_pt = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    month_label = f"{meses_pt[mes]} / {ano}"

    # Cálculo da paginação
    if mes == 1:
        prev_month, prev_year = 12, ano - 1
    else:
        prev_month, prev_year = mes - 1, ano

    if mes == 12:
        next_month, next_year = 1, ano + 1
    else:
        next_month, next_year = mes + 1, ano

    # ----------------------------
    # CARREGAR TOKEN DO BANCO
    # ----------------------------
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT google_cal_access_token, google_cal_refresh_token, google_cal_token_expiry FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    calendar_connected = bool(user and user.get("google_cal_access_token"))
    events = []
    error_msg = None

    if calendar_connected:
        access_token = user["google_cal_access_token"]
        expires_at = user.get("google_cal_token_expiry")

        # Se expiry for string (depende do driver), tenta converter
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None

        # refresh proativo se expirar em menos de 60 segundos
        need_refresh = False
        if not expires_at:
            need_refresh = True
        else:
            if expires_at <= datetime.datetime.utcnow() + datetime.timedelta(seconds=60):
                need_refresh = True

        if need_refresh:
            print("Token próximo do expiry ou sem expiry - tentando refresh proativo...")
            refreshed = refresh_google_tokens(session['user_id'])
            if refreshed and refreshed.get('access_token'):
                access_token = refreshed['access_token']
                print("Refresh proativo bem-sucedido.")
            else:
                calendar_connected = False
                error_msg = "Token expirado ou inválido. Reconecte sua Google Agenda."
                print("Refresh proativo falhou -> marcar como desconectado.")

    if calendar_connected:
        try:
            # tenta obter eventos usando access_token (novo ou antigo)
            resp = get_events_from_calendar(access_token, time_min, time_max)

            # se 401 → tenta refresh e repetir
            if resp.status_code == 401:
                print("Calendar API devolveu 401 → tentando refresh e retry...")
                refreshed = refresh_google_tokens(session['user_id'])
                if refreshed and refreshed.get('access_token'):
                    access_token = refreshed['access_token']
                    resp = get_events_from_calendar(access_token, time_min, time_max)

            if resp.status_code == 401:
                calendar_connected = False
                error_msg = "Token expirado ou inválido. Reconecte sua Google Agenda."
            else:
                resp.raise_for_status()
                items = resp.json().get("items", [])

                # Normalizar eventos
                for ev in items:
                    start_data = ev.get("start", {})
                    dt_raw = start_data.get("dateTime") or start_data.get("date") or ""

                    if "T" in dt_raw:
                        date_part, time_part = dt_raw.split("T", 1)
                        time_part = time_part[:5]
                    else:
                        date_part = dt_raw
                        time_part = ""

                    events.append({
                        "id": ev.get("id"),
                        "summary": ev.get("summary", "(Sem título)"),
                        "description": ev.get("description", "") or "",
                        "date": date_part,
                        "time": time_part
                    })

        except Exception as e:
            print("Erro ao consultar Google Calendar:", e)
            error_msg = "Erro ao carregar a agenda do Google."

    # -----------------------------------
    # CONSTRUIR ESTRUTURA DO CALENDÁRIO
    # -----------------------------------
    # Primeiro dia da semana (0=Seg → queremos 6=Sab) Google usa Domingo=0,
    # Python usa Segunda=0, então adaptamos:
    first_weekday = (first_day.weekday() + 1) % 7  # domingo=0

    # Criar dias vazios antes do dia 1
    calendar_days = []

    for _ in range(first_weekday):
        calendar_days.append({
            "day": "",
            "date": "",
            "is_today": False,
            "events": []
        })

    # Dias reais
    for dia in range(1, last_day_num + 1):
        data_str = f"{ano}-{mes:02d}-{dia:02d}"

        # eventos desse dia
        day_events = [ev for ev in events if ev["date"] == data_str]

        calendar_days.append({
            "day": dia,
            "date": data_str,
            "is_today": (data_str == hoje.strftime("%Y-%m-%d")),
            "events": day_events
        })

    return render_template(
        "agenda.html",
        calendar_connected=calendar_connected,
        calendar_days=calendar_days,
        month_label=month_label,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        error_msg=error_msg
    )


@ferramentas_bp.route('/ferramentas/google-calendar/conectar')
def conectar_google_calendar():
    """Inicia o fluxo de OAuth para conectar a Google Agenda."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    oauth = auth_routes.oauth
    if oauth is None:
        print("OAuth ainda não foi inicializado em auth_routes.oauth")
        return redirect(url_for('ferramentas.ferramentas_home'))

    redirect_uri = url_for('ferramentas.google_calendar_callback', _external=True)
    print("REDIRECT URI CALENDAR:", redirect_uri)

    return oauth.google.authorize_redirect(
        redirect_uri,
        scope="openid email profile https://www.googleapis.com/auth/calendar",
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )


@ferramentas_bp.route('/ferramentas/google-calendar/callback')
def google_calendar_callback():
    """Callback chamado pelo Google após o usuário aceitar a permissão da Agenda."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    oauth = auth_routes.oauth
    if oauth is None:
        return redirect(url_for('ferramentas.ferramentas_home'))

    # Tenta obter o token
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        print("Erro ao obter token do Google Calendar:", e)
        return redirect(url_for('ferramentas.ferramentas_home'))

    access_token = token.get('access_token')
    new_refresh_token = token.get('refresh_token')  # pode vir None
    expires_at = token.get('expires_at')

    expiry_dt = None
    if expires_at:
        try:
            expiry_dt = datetime.datetime.utcfromtimestamp(expires_at)
        except:
            expiry_dt = None

    # Buscar refresh_token atual no banco
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT google_cal_refresh_token
        FROM users
        WHERE id = %s
    """, (session['user_id'],))

    row = cursor.fetchone()
    old_refresh_token = row["google_cal_refresh_token"] if row else None

    # Se o Google NÃO enviou refresh_token novo, mantém o antigo.
    refresh_token_to_save = new_refresh_token if new_refresh_token else old_refresh_token

    # Agora salva tokens
    cursor2 = conn.cursor()
    cursor2.execute("""
        UPDATE users
        SET google_cal_access_token  = %s,
            google_cal_refresh_token = %s,
            google_cal_token_expiry  = %s
        WHERE id = %s
    """, (
        access_token,
        refresh_token_to_save,
        expiry_dt,
        session['user_id']
    ))

    conn.commit()
    cursor2.close()
    cursor.close()
    conn.close()

    print("google_calendar_callback: tokens salvos com sucesso (refresh token presente ?: {})".format(bool(refresh_token_to_save)))
    return redirect(url_for('ferramentas.ferramentas_home'))


@ferramentas_bp.route('/ferramentas/agenda/criar', methods=['POST'])
def criar_evento_agenda():
    """Cria um evento na Google Agenda do usuário."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # pega tokens do banco
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT google_cal_access_token
            FROM users
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not user or not user.get('google_cal_access_token'):
        # sem token → manda reconectar
        flash("Conecte sua Google Agenda antes de criar eventos.", "warning")
        return redirect(url_for('ferramentas.ferramentas_home'))

    access_token = user['google_cal_access_token']

    # pega dados do form
    titulo = request.form.get('titulo') or 'Atendimento'
    data = request.form.get('data')         # yyyy-mm-dd
    hora_inicio = request.form.get('hora_inicio')  # HH:MM
    hora_fim = request.form.get('hora_fim')        # HH:MM (opcional)

    if not data or not hora_inicio:
        flash("Data e hora de início são obrigatórios.", "warning")
        return redirect(url_for('ferramentas.ferramentas_home'))

    tz = 'America/Sao_Paulo'

    try:
        start_dt = datetime.datetime.fromisoformat(f"{data}T{hora_inicio}:00")
        if hora_fim:
            end_dt = datetime.datetime.fromisoformat(f"{data}T{hora_fim}:00")
        else:
            end_dt = start_dt + datetime.timedelta(minutes=50)

        # monta strings com offset -03:00 (suficiente pra dev)
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        body = {
            "summary": titulo,
            "start": {
                "dateTime": start_iso,
                "timeZone": tz
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": tz
            }
        }

        resp = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            json=body,
            timeout=10
        )

        # Se token expirou, tenta refresh e reenvia
        if resp.status_code == 401:
            print("criar_evento_agenda: 401 - tentando refresh...")
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
            print("Erro criando evento (status, body):", resp.status_code, resp.text)
        resp.raise_for_status()

        flash("Evento criado com sucesso na Google Agenda.", "success")

    except Exception as e:
        print("Erro ao criar evento na Google Calendar:", e)
        flash("Não foi possível criar o evento na Google Agenda.", "danger")

    return redirect(url_for('ferramentas.ferramentas_home'))


@ferramentas_bp.route('/ferramentas/google-calendar/desconectar', methods=['POST'])
def desconectar_google_calendar():
    """Limpa tokens da Google Agenda do usuário."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users
            SET google_cal_access_token=NULL, google_cal_refresh_token=NULL, google_cal_token_expiry=NULL
            WHERE id = %s
        """, (session['user_id'],))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    flash("Google Agenda desconectada.", "info")
    return redirect(url_for('ferramentas.ferramentas_home'))


@ferramentas_bp.route('/ferramentas/agenda/deletar', methods=['POST'])
def deletar_evento_agenda():
    """Deleta um evento na Google Calendar pelo eventId."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "not_authenticated"}), 401

    event_id = request.form.get('event_id') or (request.json and request.json.get('event_id'))
    if not event_id:
        return jsonify({"success": False, "error": "missing_event_id"}), 400

    # pega token do DB
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT google_cal_access_token FROM users WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not row or not row.get('google_cal_access_token'):
        return jsonify({"success": False, "error": "no_token"}), 400

    access_token = row['google_cal_access_token']

    # tenta deletar
    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{quote_plus(event_id)}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.delete(url, headers=headers, timeout=10)

    # se expirou token, tenta refresh e reenvia
    if resp.status_code == 401:
        refreshed = refresh_google_tokens(session['user_id'])
        if refreshed and refreshed.get('access_token'):
            headers["Authorization"] = f"Bearer {refreshed['access_token']}"
            resp = requests.delete(url, headers=headers, timeout=10)

    if resp.status_code in (200, 204):
        return jsonify({"success": True})
    else:
        try:
            return jsonify({"success": False, "status": resp.status_code, "body": resp.json()}), 400
        except Exception:
            return jsonify({"success": False, "status": resp.status_code, "body": resp.text}), 400


@ferramentas_bp.route('/ferramentas/agenda/editar', methods=['POST'])
def editar_evento_agenda():
    """Edita um evento existente na Google Calendar."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "not_authenticated"}), 401

    data = request.form or (request.json or {})
    event_id = data.get('event_id')
    titulo = data.get('titulo')
    data_day = data.get('data')    # yyyy-mm-dd
    hora_inicio = data.get('hora_inicio')  # HH:MM
    hora_fim = data.get('hora_fim')        # HH:MM (opcional)
    descricao = data.get('descricao', '')

    if not event_id or not data_day or not hora_inicio:
        return jsonify({"success": False, "error": "missing_fields"}), 400

    # pega token
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT google_cal_access_token FROM users WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not row or not row.get('google_cal_access_token'):
        return jsonify({"success": False, "error": "no_token"}), 400

    access_token = row['google_cal_access_token']
    tz = 'America/Sao_Paulo'

    try:
        start_dt = datetime.datetime.fromisoformat(f"{data_day}T{hora_inicio}:00")
        if hora_fim:
            end_dt = datetime.datetime.fromisoformat(f"{data_day}T{hora_fim}:00")
        else:
            end_dt = start_dt + datetime.timedelta(minutes=50)

        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")

        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{quote_plus(event_id)}"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        body = {
            "summary": titulo,
            "description": descricao,
            "start": {"dateTime": start_iso, "timeZone": tz},
            "end": {"dateTime": end_iso, "timeZone": tz}
        }

        resp = requests.patch(url, headers=headers, json=body, timeout=10)

        if resp.status_code == 401:
            refreshed = refresh_google_tokens(session['user_id'])
            if refreshed and refreshed.get('access_token'):
                headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                resp = requests.patch(url, headers=headers, json=body, timeout=10)

        resp.raise_for_status()
        return jsonify({"success": True, "event": resp.json()})
    except Exception as e:
        print("Erro ao editar evento:", e)
        try:
            return jsonify({"success": False, "error": str(e)}), 500
        except:
            return jsonify({"success": False, "error": "unknown"}), 500


def criar_evento_agenda_for_user(user_id, titulo, data, hora_inicio, hora_fim=None, descricao=''):
    """
    Cria um evento na Google Agenda de um usuário específico (usado no fluxo público).
    Retorna (True, response_json) em caso de sucesso, ou (False, erro) em caso de falha.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT google_cal_access_token
            FROM users
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not user or not user.get('google_cal_access_token'):
        return False, "no_token"

    access_token = user['google_cal_access_token']
    tz = 'America/Sao_Paulo'

    try:
        start_dt = datetime.datetime.fromisoformat(f"{data}T{hora_inicio}:00")
        if hora_fim:
            end_dt = datetime.datetime.fromisoformat(f"{data}T{hora_fim}:00")
        else:
            end_dt = start_dt + datetime.timedelta(minutes=50)

        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        body = {
            "summary": titulo,
            "description": descricao or "",
            "start": {"dateTime": start_iso, "timeZone": tz},
            "end":   {"dateTime": end_iso,   "timeZone": tz}
        }

        resp = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            json=body,
            timeout=10
        )

        if resp.status_code == 401:
            print("criar_evento_agenda_for_user: 401 - tentando refresh...")
            refreshed = refresh_google_tokens(user_id)
            if refreshed and refreshed.get('access_token'):
                headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                resp = requests.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers=headers,
                    json=body,
                    timeout=10
                )

        resp.raise_for_status()
        return True, resp.json()
    except Exception as e:
        print("Erro ao criar evento automático na agenda:", e)
        return False, str(e)

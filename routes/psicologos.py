# routes/psicologos.py
from flask import Blueprint, render_template, request, session
from db.db import get_db_connection
import math
import random
from datetime import datetime, timedelta, date, time as dt_time, timezone
import re
from urllib.parse import urlparse, parse_qs

psicologos_bp = Blueprint('psicologos', __name__)


# helper: parse ISO datetimes do Google (aceita offsets e 'Z') -> timestamp UTC (segundos)
def iso_to_utc_ts(iso_str):
    if not iso_str:
        return None
    try:
        # normaliza 'Z' -> +00:00 para fromisoformat
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            # assume UTC if no tz (unlikely for dateTime), so treat as UTC
            dt = dt.replace(tzinfo=timezone.utc)
        # converte para UTC
        dt_utc = dt.astimezone(timezone.utc)
        return int(dt_utc.timestamp())
    except Exception as e:
        # se falhar, tenta parse de date-only (all-day event)
        try:
            d = datetime.fromisoformat(iso_str).date()
            # marcar como dia todo -> 00:00 UTC do dia (pode bloquear todos os slots; depende do seu critério)
            dt = datetime.combine(d, dt_time(0,0), tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            print("iso_to_utc_ts parse fail:", e, iso_str)
            return None

# comparador de conflito usando timestamps UTC
def slot_conflicts_with_events_ts(slot_start_ts, slot_end_ts, events_ts):
    # events_ts: list of {'start_ts': int, 'end_ts': int}
    for ev in events_ts:
        s = ev.get('start_ts'); e = ev.get('end_ts')
        if s is None or e is None:
            continue
        # overlap: slot_start < ev_end and slot_end > ev_start
        if slot_start_ts < e and slot_end_ts > s:
            return True
    return False

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


# função auxiliar: verifica se um slot datetime (start,end) colide com evento (start,end)
def slot_conflicts_with_events(slot_start_dt, slot_end_dt, events):
    for ev in events:
        try:
            ev_start = datetime.fromisoformat(ev['start'].replace('Z', '+00:00')) if ev['start'].endswith('Z') else datetime.fromisoformat(ev['start'])
            ev_end = datetime.fromisoformat(ev['end'].replace('Z', '+00:00')) if ev['end'].endswith('Z') else datetime.fromisoformat(ev['end'])
            # se overlap
            if slot_start_dt < ev_end and slot_end_dt > ev_start:
                return True
        except Exception as e:
            # se parse falhar, evita bloquear por segurança
            print("parse event fail", e, ev)
            continue
    return False

@psicologos_bp.route('/psicologo/<int:profile_id>')
def perfil_publico(profile_id):
    import json
    from routes.ferramentas import refresh_google_tokens, get_events_from_calendar

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, u.name, u.crp, u.id AS user_id,
               u.google_cal_access_token, u.google_cal_refresh_token, u.google_cal_token_expiry
        FROM profiles p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (profile_id,))
    profile = cursor.fetchone()

    # calcula video embed (se houver)
    profile_video_url = profile.get('video_url') if profile else None
    video_embed = youtube_embed_from_url(profile_video_url)
    # adiciona ao dict para o template
    if profile is not None:
        profile['video_embed_url'] = video_embed
    else:
        profile = {'video_embed_url': video_embed}

    if not profile:
        cursor.close(); conn.close()
        return "Perfil não encontrado", 404

    # fetch metadata
    cursor.execute("""SELECT a.* FROM approaches a JOIN profile_approaches pa ON pa.approach_id = a.id WHERE pa.profile_id = %s""", (profile_id,))
    abordagens = cursor.fetchall()
    cursor.execute("""SELECT e.* FROM experiencias e JOIN profile_experiencias pe ON pe.experiencia_id = e.id WHERE pe.profile_id = %s""", (profile_id,))
    experiencias = cursor.fetchall()
    cursor.execute("""SELECT p.* FROM publicos_alvo p JOIN profile_publicos_alvo pp ON pp.publico_id = p.id WHERE pp.profile_id = %s""", (profile_id,))
    publicos = cursor.fetchall()

    # parse availability
    try:
        availability = json.loads(profile['availability']) if profile.get('availability') else {}
    except Exception as e:
        print("availability JSON parse error:", e)
        availability = {}

    # GET busy events from Google Calendar and convert to UTC timestamps
    busy_events_ts = []  # list of {'start_ts': int, 'end_ts': int}
    access_token = profile.get('google_cal_access_token')
    calendar_connected = bool(access_token)
    if calendar_connected:
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=30)).isoformat() + 'Z'

            resp = get_events_from_calendar(access_token, time_min, time_max)
            # if unauthorized try refresh
            if resp.status_code == 401:
                refreshed = refresh_google_tokens(profile['user_id'])
                if refreshed:
                    access_token = refreshed['access_token']
                    resp = get_events_from_calendar(access_token, time_min, time_max)

            resp.raise_for_status()
            items = resp.json().get('items', [])
            for ev in items:
                start_raw = ev.get('start', {}).get('dateTime') or ev.get('start', {}).get('date') or None
                end_raw = ev.get('end', {}).get('dateTime') or ev.get('end', {}).get('date') or None
                s_ts = iso_to_utc_ts(start_raw) if start_raw else None
                e_ts = iso_to_utc_ts(end_raw) if end_raw else None
                if s_ts and e_ts:
                    busy_events_ts.append({'start_ts': s_ts, 'end_ts': e_ts})
        except Exception as e:
            print("Erro ao consultar Google Calendar (perfil_publico):", e)
            busy_events_ts = []

    cursor.close()
    conn.close()

    # ---------- construir páginas de dias com slots (server-side) ----------
    window_days = 21
    page_size = 7
    start_date = date.today()

    all_days = []
    for offset in range(window_days):
        d = start_date + timedelta(days=offset)
        py_weekday = d.weekday()  # 0=Mon
        weekday_key = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][py_weekday]
        ranges = availability.get(weekday_key, [])
        slots = []
        for r in ranges:
            try:
                s_raw = r.get('start') or '00:00'
                e_raw = r.get('end') or '00:00'
                s_h, s_m = map(int, s_raw.split(':'))
                e_h, e_m = map(int, e_raw.split(':'))
                first_hour = s_h + (1 if s_m > 0 else 0)
                last_start = e_h - 1 if e_m == 0 else e_h
                for hour in range(first_hour, last_start + 1):
                    # build slot start/end in psychologist's local timezone: assume -03:00 (America/Sao_Paulo)
                    # Create aware dt with tz offset -03:00 then get UTC timestamp
                    tz_offset = timedelta(hours=-3)
                    slot_start_local = datetime.combine(d, dt_time(hour=hour, minute=0, tzinfo=timezone(tz_offset)))
                    slot_end_local = slot_start_local + timedelta(hours=1)
                    slot_start_ts = int(slot_start_local.astimezone(timezone.utc).timestamp())
                    slot_end_ts = int(slot_end_local.astimezone(timezone.utc).timestamp())

                    # check conflict using timestamps
                    if slot_conflicts_with_events_ts(slot_start_ts, slot_end_ts, busy_events_ts):
                        continue

                    slots.append({
                        'time': f"{hour:02d}:00",
                        'start_iso': slot_start_local.isoformat(),
                        'start_ts': slot_start_ts
                    })
            except Exception as e:
                print("Erro gerando slots:", e, r)
                continue

        all_days.append({
            'date': d.isoformat(),
            'weekday': weekday_key,
            'label': d.strftime('%a %d/%m'),
            'slots': slots
        })

    # pages
    pages = [ all_days[i:i+page_size] for i in range(0, len(all_days), page_size) ]
    total_pages = len(pages)
    page = int(request.args.get('page', 1))
    page = max(1, min(page, total_pages)) if pages else 1
    page_index = page - 1
    current_page_days = pages[page_index] if pages else []

    # if AJAX requested, return only fragment for calendar (render partial)
    if request.args.get('ajax'):
        return render_template('partials/_calendar_fragment.html',
                               current_page_days=current_page_days,
                               profile=profile,
                               current_page=page,
                               total_pages=total_pages)

    # otherwise render full page (original template), passing pages data too if needed
    return render_template("perfil_publico.html",
                           profile=profile,
                           abordagens=abordagens,
                           experiencias=experiencias,
                           publicos=publicos,
                           pages=pages,
                           current_page=page,
                           total_pages=total_pages,
                           current_page_days=current_page_days)


def youtube_embed_from_url(url):
    """
    Recebe um link do YouTube em vários formatos e devolve a URL de embed:
      - https://www.youtube.com/watch?v=VIDEOID
      - https://youtu.be/VIDEOID
      - https://www.youtube.com/embed/VIDEOID
    Retorna None se não reconhecer.
    """
    if not url:
        return None
    u = url.strip()
    try:
        parsed = urlparse(u)
        host = parsed.netloc.lower()
        # youtu.be short link
        if 'youtu.be' in host:
            vid = parsed.path.lstrip('/')
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
            return None
        # youtube.com watch?v=VIDEOID
        if 'youtube.com' in host:
            # if /watch?v=
            if parsed.path == '/watch':
                qs = parse_qs(parsed.query)
                vid_list = qs.get('v')
                if vid_list:
                    return f"https://www.youtube.com/embed/{vid_list[0]}"
            # if /embed/VIDEOID
            m = re.search(r'/embed/([^/?&]+)', parsed.path)
            if m:
                return f"https://www.youtube.com/embed/{m.group(1)}"
            # sometimes path is /v/VIDEOID
            m2 = re.search(r'/v/([^/?&]+)', parsed.path)
            if m2:
                return f"https://www.youtube.com/embed/{m2.group(1)}"
        # fallback: try regex for common id pattern
        m3 = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|$)', u)
        if m3:
            return f"https://www.youtube.com/embed/{m3.group(1)}"
    except Exception:
        return None
    return None

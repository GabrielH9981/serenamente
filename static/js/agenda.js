// static/js/agenda.js

// usa as configs injetadas no template
const EDIT_URL = (window.AGENDA_CONFIG && window.AGENDA_CONFIG.editarUrl) || '/';
const DELETE_URL = (window.AGENDA_CONFIG && window.AGENDA_CONFIG.deletarUrl) || '/';
const CREATE_URL = (window.AGENDA_CONFIG && window.AGENDA_CONFIG.criarUrl) || '/';

// eventsByDate deve ter sido definido inline como window.eventsByDate
const eventsByDate = window.eventsByDate || {};

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function renderEventCard(ev, container) {
    const card = document.createElement('div');
    card.className = 'mb-2 p-2 rounded border';

    const top = document.createElement('div');
    top.className = 'd-flex justify-content-between align-items-center';

    const titleDiv = document.createElement('div');
    titleDiv.innerHTML = '<strong>' + (ev.time ? (ev.time + ' — ') : '') + '</strong>' + escapeHtml(ev.summary);
    top.appendChild(titleDiv);

    const actions = document.createElement('div');

    const btnEdit = document.createElement('button');
    btnEdit.className = 'btn btn-sm btn-outline-primary me-2';
    btnEdit.textContent = 'Editar';
    btnEdit.type = 'button';
    btnEdit.addEventListener('click', function () {
        openEditForm(ev, card);
    });
    actions.appendChild(btnEdit);

    const btnDelete = document.createElement('button');
    btnDelete.className = 'btn btn-sm btn-outline-danger';
    btnDelete.textContent = 'Excluir';
    btnDelete.type = 'button';
    btnDelete.addEventListener('click', function () {
        if (!confirm('Confirmar exclusão deste evento?')) return;
        deleteEvent(ev.id, card);
    });
    actions.appendChild(btnDelete);

    top.appendChild(actions);
    card.appendChild(top);

    if (ev.description) {
        const desc = document.createElement('div');
        desc.className = 'text-muted small mt-1';
        desc.innerHTML = escapeHtml(ev.description);
        card.appendChild(desc);
    }

    container.appendChild(card);
}

function openEditForm(ev, cardElement) {
    cardElement.innerHTML = '';

    const form = document.createElement('form');
    form.className = 'mb-2';
    form.innerHTML = `
      <div class="mb-2">
        <label class="form-label small mb-1">Título</label>
        <input type="text" name="titulo" class="form-control form-control-sm" value="${escapeHtml(ev.summary)}" required>
      </div>
      <div class="row g-2">
        <div class="col-6">
          <label class="form-label small mb-1">Início</label>
          <input type="time" name="hora_inicio" class="form-control form-control-sm" value="${ev.time || ''}" required>
        </div>
        <div class="col-6">
          <label class="form-label small mb-1">Fim</label>
          <input type="time" name="hora_fim" class="form-control form-control-sm">
        </div>
      </div>
      <div class="mb-2 mt-2">
        <label class="form-label small mb-1">Descrição</label>
        <textarea name="descricao" class="form-control form-control-sm" rows="2">${escapeHtml(ev.description || '')}</textarea>
      </div>
      <div class="d-flex justify-content-end gap-2">
        <button type="button" class="btn btn-sm btn-secondary btn-cancel">Cancelar</button>
        <button type="submit" class="btn btn-sm btn-primary">Salvar</button>
      </div>
    `;

    form.querySelector('.btn-cancel').addEventListener('click', function () {
        cardElement.innerHTML = '';
        renderEventCard(ev, cardElement.parentElement);
    });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const fd = new FormData(form);
        const payload = {
            event_id: ev.id,
            titulo: fd.get('titulo'),
            data: document.getElementById('modalData').value,
            hora_inicio: fd.get('hora_inicio'),
            hora_fim: fd.get('hora_fim'),
            descricao: fd.get('descricao')
        };

        fetch(EDIT_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }).then(r => r.json()).then(res => {
            if (res && res.success) {
                ev.summary = payload.titulo;
                ev.time = payload.hora_inicio;
                ev.description = payload.descricao;
                cardElement.innerHTML = '';
                renderEventCard(ev, cardElement.parentElement);
                // atualizar célula do calendário
                renderDayCell(payload.data);
            } else {
                alert('Erro ao editar evento.');
            }
        }).catch(err => {
            console.error(err);
            alert('Erro ao editar evento.');
        });
    });

    cardElement.appendChild(form);
}

function renderDayCell(date) {
    const cell = document.querySelector(`.day-box[data-date="${date}"]`);
    if (!cell) return;

    const container = cell.querySelector('.day-events-container');
    if (!container) return;

    container.innerHTML = '';

    const evs = eventsByDate[date] || [];

    const maxShow = 2;
    const toShow = evs.slice(0, maxShow);

    toShow.forEach(ev => {
        const pill = document.createElement('div');
        pill.className = 'event-pill';
        pill.title = ev.summary;
        pill.textContent = (ev.time ? (ev.time + ' ') : '') + ev.summary;
        pill.addEventListener('click', function(e){ e.stopPropagation(); openModal(date); });
        container.appendChild(pill);
    });

    if (evs.length > maxShow) {
        const more = document.createElement('div');
        more.className = 'event-pill more-pill';
        more.textContent = '+' + (evs.length - maxShow) + ' Mais';
        more.title = 'Abrir lista completa';
        more.addEventListener('click', function(e){
            e.stopPropagation();
            openModal(date);
        });
        container.appendChild(more);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // renderizar células do mês
    document.querySelectorAll('.day-box[data-date]').forEach(box => {
        const d = box.getAttribute('data-date');
        renderDayCell(d);
    });
});

function deleteEvent(eventId, cardElement) {
    fetch(DELETE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_id: eventId })
    }).then(r => r.json()).then(res => {
        if (res && res.success) {
            const date = document.getElementById('modalData').value;
            if (eventsByDate[date]) {
                eventsByDate[date] = eventsByDate[date].filter(x => x.id !== eventId);
            }
            cardElement.remove();
            renderDayCell(date);
        } else {
            alert('Erro ao excluir evento.');
            console.log(res);
        }
    }).catch(err => {
        console.error(err);
        alert('Erro ao excluir evento.');
    });
}

function openModal(date) {
    document.getElementById("modalData").value = date;
    document.getElementById("modalDateLabel").textContent = date;

    const list = document.getElementById('dayEventsList');
    list.innerHTML = '';

    const evs = eventsByDate[date] || [];

    if (evs.length === 0) {
        list.innerHTML = '<div class="alert alert-info mb-0">Nenhum evento programado neste dia.</div>';
    } else {
        evs.forEach(ev => {
            renderEventCard(ev, list);
        });
    }

    // usa bootstrap global (deve ter sido carregado antes)
    const bsModal = new bootstrap.Modal(document.getElementById('modalCriar'));
    bsModal.show();
}

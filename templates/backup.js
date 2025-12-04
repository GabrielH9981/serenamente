<script>
  let selected = null;
  function clearSelected() {
    document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected', 'btn-success'));
    selected = null;
    document.getElementById('selectedInfo').textContent = 'Selecione uma data';
    const waBtn = document.getElementById('waButton');
    if (waBtn) { waBtn.disabled = true; waBtn.onclick = null; }
  }

  function onSlotClick(e) {
    const btn = e.currentTarget;
    clearSelected();
    btn.classList.add('selected', 'btn-success');
    const date = btn.dataset.date; // yyyy-mm-dd
    const time = btn.dataset.time; // HH:MM
    selected = { date, time };
    const dt = new Date(date + 'T' + time); // navegador interpreta local timezone
    const opts = { weekday: 'long', day:'2-digit', month:'2-digit' };
    document.getElementById('selectedInfo').textContent = `${dt.toLocaleDateString('pt-BR', opts)} às ${time}`;
    const waBtn = document.getElementById('waButton');
    if (waBtn) {
      waBtn.disabled = false;
      const waNumber = waBtn.dataset.waNumber;
      waBtn.onclick = function() {
        const dayLabel = dt.toLocaleDateString('pt-BR', { weekday:'long' });
        const msg = `Olá, gostaria de agendar uma sessão na ${dayLabel} ${date} às ${time}.`;
        const url = `https://wa.me/${waNumber}?text=${encodeURIComponent(msg)}`;
        window.open(url, '_blank');
      };
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.slot-btn').forEach(b => b.addEventListener('click', onSlotClick));
    // reset caso mude de página (navegação full reload); já está OK
  });
</script>

 Script: gera slots de 1h, filtra busy events e monta a UI
<script>
  // days mapping para exibição
  const DAY_LABELS = {
    'monday': 'Segunda',
    'tuesday': 'Terça',
    'wednesday': 'Quarta',
    'thursday': 'Quinta',
    'friday': 'Sexta',
    'saturday': 'Sábado',
    'sunday': 'Domingo'
  };

  // pega availability do backend (string JSON ou vazio)
  const availabilityRaw = {{ availability | tojson | safe if availability is defined and availability else 'null' }};

  console.log("DEBUG: availabilityRaw =", availabilityRaw);
  console.log("DEBUG: busy_events =", {{ busy_events | tojson | safe if busy_events is defined else '[]' }});


  // busyEvents do backend: lista de {start: ISO, end: ISO}
  const busyEvents = {{ busy_events | tojson | safe if busy_events is defined else '[]' }};

  // converte busy events para marcação por weekday+hour (remove slots cuja hora esteja coberta por evento)
  function buildBusyMap(events) {
    const map = {}; // map[weekday][hour] = true
    events.forEach(ev => {
      try {
        const s = new Date(ev.start);
        const e = new Date(ev.end);
        // itera horas entre start e end (arredonda para hora inteira)
        let cur = new Date(s);
        // if minutes > 0, começar no hour curHour (ceil)
        if (cur.getMinutes() > 0 || cur.getSeconds() > 0) {
          cur.setHours(cur.getHours()+1, 0, 0, 0);
        } else {
          cur.setMinutes(0,0,0);
        }
        while (cur < e) {
          const weekday = cur.getDay(); // 0=domingo .. 6=sabado
          // convert to our keys: sunday, monday...
          const key = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday'][weekday];
          const hour = cur.getHours(); // 0..23
          map[key] = map[key] || {};
          map[key][hour] = true;
          cur.setHours(cur.getHours()+1);
        }
      } catch (err) {
        console.log('erro ao parsear busy event', ev, err);
      }
    });
    return map;
  }

  // gera slots de 1h a partir de ranges no formato HH:MM
  function generateHourlySlotsForRange(startStr, endStr) {
    const slots = [];
    // parse HH:MM
    const [sH, sM] = startStr.split(':').map(Number);
    const [eH, eM] = endStr.split(':').map(Number);

    // calcular primeira hora: se minutos > 0 -> ceil para próxima hora, senão usar sH
    let curHour = (sM > 0) ? sH + 1 : sH;
    // calcular limite: se eM == 0 -> last slot starts at eH - 1, caso contrário last slot starts at eH
    let lastStartHour = (eM === 0) ? (eH - 1) : eH;
    for (let h = curHour; h <= lastStartHour; h++) {
      if (h >= 0 && h <= 23) {
        slots.push(('0' + h).slice(-2) + ':00');
      }
    }
    return slots;
  }

  // cria botões de slots por dia
  function renderAvailability(availabilityObj, busyMap) {
    const container = document.getElementById('availability-days');
    if (!container) return;

    container.innerHTML = ''; // limpa

    for (const dayKey of ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']) {
      const dayRanges = availabilityObj[dayKey] || [];
      const dayWrapper = document.createElement('div');
      const dayTitle = document.createElement('div');
      dayTitle.className = 'd-flex align-items-center mb-2';
      dayTitle.innerHTML = `<strong class="me-2">${DAY_LABELS[dayKey]}</strong>`;
      dayWrapper.appendChild(dayTitle);

      const slotsRow = document.createElement('div');
      slotsRow.className = 'd-flex flex-wrap gap-2';

      const usedHourMap = busyMap[dayKey] || {};

      // gerar todos os slots de todas as ranges
      let totalSlots = 0;
      dayRanges.forEach(r => {
        const s = r.start || '00:00';
        const e = r.end || '00:00';
        const slots = generateHourlySlotsForRange(s, e);
        slots.forEach(slot => {
          const hour = parseInt(slot.split(':')[0], 10);
          // filtrar se ocupado (busyMap)
          if (usedHourMap[hour]) return;
          totalSlots += 1;
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'btn btn-outline-primary btn-sm slot-btn';
          btn.dataset.day = dayKey;
          btn.dataset.time = slot; // formato HH:MM
          btn.textContent = `${parseInt(slot.split(':')[0],10)}h`;
          btn.onclick = onSlotClick;
          slotsRow.appendChild(btn);
        });
      });

      if (totalSlots === 0) {
        const empty = document.createElement('div');
        empty.className = 'text-muted small';
        empty.textContent = 'Nenhum horário disponível.';
        dayWrapper.appendChild(empty);
      } else {
        dayWrapper.appendChild(slotsRow);
      }

      container.appendChild(dayWrapper);
    }
  }

  // seleção: apenas 1 slot por vez
  let selectedSlot = null; // { day: 'monday', time: '08:00' }

  function onSlotClick(e) {
    const btn = e.currentTarget;
    // desmarca todos
    document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('btn-success', 'selected'));
    // marca clicado
    btn.classList.add('btn-success', 'selected');
    selectedSlot = { day: btn.dataset.day, time: btn.dataset.time };
    updateWhatsAppButton();
  }

  // atualiza href do botão de WhatsApp com mensagem já com o horário selecionado
  function updateWhatsAppButton() {
    const waBtn = document.getElementById('waButton');
    if (!waBtn) return;
    const waNumber = waBtn.dataset.waNumber; // já com DDI
    // base message — personalize como quiser
    let message = 'Olá, gostaria de agendar uma sessão.';
    if (selectedSlot) {
      const dayLabel = DAY_LABELS[selectedSlot.day] || selectedSlot.day;
      // exemplo: "Segunda às 08:00"
      message += ` Meu horário preferido: ${dayLabel} às ${selectedSlot.time}.`;
    }
    // opcional: acrescentar nome do paciente (se tiver no session) - aqui deixamos genérico
    const url = `https://wa.me/${waNumber}?text=${encodeURIComponent(message)}`;
    // transformamos botão em link abridor
    waBtn.onclick = function() {
      window.open(url, '_blank');
    };
  }

  // inicia: parse availability e busyEvents, renderiza
  (function initAvailability() {
  let availabilityObj = {};
  try {
    if (!availabilityRaw) {
      availabilityObj = {};
    } else if (typeof availabilityRaw === 'string') {
      // se por algum motivo ainda for string JSON, tenta parsear
      try {
        availabilityObj = JSON.parse(availabilityRaw);
      } catch (e) {
        console.error('availabilityRaw é string mas JSON inválido:', e);
        availabilityObj = {};
      }
    } else {
      // já é objeto
      availabilityObj = availabilityRaw;
    }
  } catch (err) {
    console.log('Erro parse availability (catch all):', err);
    availabilityObj = {};
  }

  const busyMap = buildBusyMap(busyEvents || []);
  console.log('DEBUG: busyMap =', busyMap);
  renderAvailability(availabilityObj, busyMap);
  updateWhatsAppButton();
})();

</script>
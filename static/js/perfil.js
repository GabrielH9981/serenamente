// static/js/perfil.js

// ---------- Cropper ----------
let cropper;

document.addEventListener('DOMContentLoaded', function () {
    const inputImage = document.getElementById('inputImage');
    const imagePreview = document.getElementById('imagePreview');
    const croppedInput = document.getElementById('croppedImageInput');
    const finalPreview = document.getElementById('finalPreview');
    const cropperModal = new bootstrap.Modal(document.getElementById('cropperModal'));

    if (inputImage) {
        inputImage.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function (event) {
                imagePreview.src = event.target.result;

                imagePreview.onload = function () {
                    cropperModal.show();

                    setTimeout(() => {
                        if (cropper) cropper.destroy();
                        cropper = new Cropper(imagePreview, {
                            aspectRatio: 1,
                            viewMode: 1,
                            autoCropArea: 1
                        });
                    }, 200);
                };
            };
            reader.readAsDataURL(file);
        });
    }

    const cropConfirmBtn = document.getElementById('cropConfirmBtn');
    if (cropConfirmBtn) {
        cropConfirmBtn.addEventListener('click', function () {
            const canvas = cropper.getCroppedCanvas({ width: 300, height: 300 });
            const dataUrl = canvas.toDataURL('image/jpeg');
            croppedInput.value = dataUrl;
            finalPreview.src = dataUrl;
            finalPreview.style.display = 'block';
            document.getElementById('previewLabel').style.display = 'block';

            const originalPic = document.getElementById('originalProfilePic');
            const originalText = document.getElementById('originalText');
            if (originalPic) originalPic.style.display = 'none';
            if (originalText) originalText.style.display = 'none';
        });
    }

    // --- Lógica de localização (online / presencial + ViaCEP) ---
    const chkOnline = document.getElementById('atendimentoOnline');
    const chkPresencial = document.getElementById('atendimentoPresencial');
    const onlineFields = document.getElementById('onlineFields');
    const presencialFields = document.getElementById('presencialFields');
    const cepPresencial = document.getElementById('cepPresencial');
    const cidadePresencial = document.getElementById('cidadePresencial');
    const estadoPresencial = document.getElementById('estadoPresencial');
    const ruaPresencial = document.getElementById('ruaPresencial');
    const whatsappInput = document.getElementById('whatsappInput');

    // Máscara para WhatsApp
    if (whatsappInput && window.Inputmask) {
        Inputmask({ mask: "(99) 99999-9999" }).mask(whatsappInput);
    }

    function updateLocationFields() {
        if (chkOnline && chkOnline.checked && (!chkPresencial || !chkPresencial.checked)) {
            onlineFields?.classList.remove('d-none');
        } else {
            onlineFields?.classList.add('d-none');
        }

        if (chkPresencial && chkPresencial.checked) {
            presencialFields?.classList.remove('d-none');
        } else {
            presencialFields?.classList.add('d-none');
        }
    }

    if (chkOnline) chkOnline.addEventListener('change', updateLocationFields);
    if (chkPresencial) chkPresencial.addEventListener('change', updateLocationFields);
    updateLocationFields();

    // ViaCEP
    if (cepPresencial) {
        cepPresencial.addEventListener('input', function () {
            let v = cepPresencial.value.replace(/\D/g, '');
            if (v.length > 8) v = v.slice(0, 8);
            if (v.length > 5) v = v.slice(0, 5) + '-' + v.slice(5);
            cepPresencial.value = v;
        });

        cepPresencial.addEventListener('blur', function () {
            const cepNum = cepPresencial.value.replace(/\D/g, '');
            if (cepNum.length !== 8) return;

            fetch(`https://viacep.com.br/ws/${cepNum}/json/`)
                .then(resp => resp.json())
                .then(data => {
                    if (data.erro) return;
                    if (data.logradouro && ruaPresencial && ruaPresencial.value.trim() === '') {
                        ruaPresencial.value = data.logradouro;
                    }
                    if (data.localidade && cidadePresencial && cidadePresencial.value.trim() === '') {
                        cidadePresencial.value = data.localidade;
                    }
                    if (data.uf && estadoPresencial && !estadoPresencial.value) {
                        estadoPresencial.value = data.uf;
                    }
                })
                .catch(err => console.log('Erro ao consultar ViaCEP', err));
        });
    }

    // --- Exibir ou esconder seção de horários conforme modo de agendamento ---
    const schedulingSelect = document.getElementById('schedulingMode');
    const availabilitySection = document.getElementById('availabilitySection');

    function updateSchedulingVisibility() {
        if (!schedulingSelect || !availabilitySection) return;
        const mode = schedulingSelect.value || 'manual';
        if (mode === 'none') {
            availabilitySection.classList.add('d-none');
        } else {
            availabilitySection.classList.remove('d-none');
        }
    }

    if (schedulingSelect) {
        schedulingSelect.addEventListener('change', updateSchedulingVisibility);
        updateSchedulingVisibility();
    }

    // Contadores de caracteres
    attachCharCounters();
});

// ---------- Availability schedule logic ----------
const DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];

function addRange(dayKey, start = '', end = '') {
    const container = document.getElementById(`day-${dayKey}`);
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'd-flex align-items-center mb-2 time-range';

    const inputStart = document.createElement('input');
    inputStart.type = 'time';
    inputStart.className = 'form-control form-control-sm me-2 range-start';
    inputStart.value = start;

    const dash = document.createElement('span');
    dash.className = 'me-2';
    dash.textContent = '—';

    const inputEnd = document.createElement('input');
    inputEnd.type = 'time';
    inputEnd.className = 'form-control form-control-sm me-2 range-end';
    inputEnd.value = end;

    const btnRemove = document.createElement('button');
    btnRemove.type = 'button';
    btnRemove.className = 'btn btn-sm btn-outline-danger';
    btnRemove.innerHTML = '<i class="bi bi-trash"></i>';
    btnRemove.onclick = function() { removeRange(btnRemove); };

    wrapper.appendChild(inputStart);
    wrapper.appendChild(dash);
    wrapper.appendChild(inputEnd);
    wrapper.appendChild(btnRemove);

    container.appendChild(wrapper);
}

function removeRange(buttonEl) {
    const wrapper = buttonEl.closest('.time-range');
    if (wrapper) wrapper.remove();
}

function serializeAvailability() {
    const obj = {};
    for (const day of DAYS) {
        const dayContainer = document.getElementById(`day-${day}`);
        const ranges = [];
        if (!dayContainer) { obj[day] = ranges; continue; }

        const wrappers = dayContainer.querySelectorAll('.time-range');
        wrappers.forEach(w => {
            const startInput = w.querySelector('.range-start');
            const endInput = w.querySelector('.range-end');
            const startVal = startInput ? startInput.value : '';
            const endVal = endInput ? endInput.value : '';
            if (startVal && endVal) {
                ranges.push({ start: startVal, end: endVal });
            }
        });
        obj[day] = ranges;
    }
    document.getElementById('availabilityInput').value = JSON.stringify(obj);
    return obj;
}

// Submeter: serializa disponibilidade antes do submit
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function (e) {
            serializeAvailability();
        });
    });

    // Ao carregar, popula os ranges já salvos (se houver)
    try {
        const hidden = document.getElementById('availabilityInput');
        if (hidden && hidden.value) {
            const parsed = JSON.parse(hidden.value);
            for (const day of DAYS) {
                if (parsed[day] && Array.isArray(parsed[day])) {
                    parsed[day].forEach(r => {
                        addRange(day, r.start || '', r.end || '');
                    });
                }
            }
        }
    } catch (err) {
        console.log('Nenhuma disponibilidade pré-carregada ou JSON inválido.');
    }
});

// ---------- Char counters ----------
function attachCharCounters() {
    document.querySelectorAll('[maxlength]').forEach(el => {
        // evitar múltiplos badges
        if (el._hasCounter) return;

        const limit = parseInt(el.getAttribute('maxlength')||0, 10);
        const counter = document.createElement('div');
        counter.className = 'char-counter';
        counter.textContent = `${(el.value||'').length}/${limit}`;

        // se o elemento estiver dentro de .input-group, insere depois do .input-group
        const inputGroup = el.closest('.input-group');
        const insertAfterEl = inputGroup || el;
        insertAfterEl.insertAdjacentElement('afterend', counter);

        const update = () => {
            const len = el.value ? el.value.length : 0;
            counter.textContent = `${len}/${limit}`;
        };
        el.addEventListener('input', update);
        el._hasCounter = true;
        // chamada inicial
        update();
    });
}

// ---------- Preview via AJAX ----------
document.addEventListener('DOMContentLoaded', function() {
    const previewBtn = document.getElementById('previewProfileBtn');
    if (!previewBtn) return;

    previewBtn.addEventListener('click', async function (e) {
        const modalBody = document.getElementById('previewModalBody');
        modalBody.innerHTML = '<div class="text-center text-muted py-4">Gerando prévia...</div>';

        try {
            // garante availability atualizada
            serializeAvailability();

            const form = document.getElementById('perfilForm');
            const fd = new FormData(form);

            // Pega a URL do botão ou usa uma URL padrão
            const previewUrl = previewBtn.dataset.previewUrl || '/perfil/preview';

            const resp = await fetch(previewUrl, {
                method: 'POST',
                body: fd,
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!resp.ok) {
                const text = await resp.text().catch(()=>null);
                modalBody.innerHTML = `<div class="alert alert-danger">Erro ao gerar prévia. (${resp.status})<br><pre style="white-space:pre-wrap">${text || ''}</pre></div>`;
                return;
            }

            const html = await resp.text();
            modalBody.innerHTML = html;
        } catch (err) {
            console.error('preview error', err);
            modalBody.innerHTML = `<div class="alert alert-danger">Erro ao gerar prévia. Veja o console para detalhes.</div>`;
        }
    });
});
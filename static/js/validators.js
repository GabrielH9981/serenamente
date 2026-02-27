// static/js/validators.js
// Validações frontend para auxiliar o usuário

// Validação de CPF
function validarCPF(cpf) {
    cpf = cpf.replace(/\D/g, '');
    
    if (cpf.length !== 11) return false;
    if (/^(\d)\1{10}$/.test(cpf)) return false; // todos iguais
    
    // Valida primeiro dígito
    let soma = 0;
    for (let i = 0; i < 9; i++) {
        soma += parseInt(cpf.charAt(i)) * (10 - i);
    }
    let resto = 11 - (soma % 11);
    let digito1 = resto >= 10 ? 0 : resto;
    
    if (digito1 !== parseInt(cpf.charAt(9))) return false;
    
    // Valida segundo dígito
    soma = 0;
    for (let i = 0; i < 10; i++) {
        soma += parseInt(cpf.charAt(i)) * (11 - i);
    }
    resto = 11 - (soma % 11);
    let digito2 = resto >= 10 ? 0 : resto;
    
    return digito2 === parseInt(cpf.charAt(10));
}

// Validação de email
function validarEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

// Validação de telefone brasileiro
function validarTelefone(telefone) {
    const numeros = telefone.replace(/\D/g, '');
    // Aceita: 11 dígitos (DDD + 9 + 8) ou 10 dígitos (DDD + 8)
    if (numeros.length < 10 || numeros.length > 11) return false;
    // Se tiver 11 dígitos, o terceiro deve ser 9
    if (numeros.length === 11 && numeros.charAt(2) !== '9') return false;
    return true;
}

// Validação de URL
function validarURL(url) {
    if (!url) return true; // URL vazia é válida (campo opcional)
    try {
        // Adiciona https:// se não tiver protocolo
        if (!url.match(/^https?:\/\//i)) {
            url = 'https://' + url;
        }
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

// Adiciona feedback visual ao campo
function setFieldFeedback(input, isValid, message = '') {
    input.classList.remove('is-valid', 'is-invalid');
    
    // Remove feedback anterior
    const feedback = input.parentElement.querySelector('.invalid-feedback, .valid-feedback');
    if (feedback) feedback.remove();
    
    if (isValid === null) return; // Sem validação ainda
    
    input.classList.add(isValid ? 'is-valid' : 'is-invalid');
    
    if (!isValid && message) {
        const div = document.createElement('div');
        div.className = 'invalid-feedback';
        div.textContent = message;
        input.parentElement.appendChild(div);
    }
}

// Validação em tempo real para CPF
function setupCPFValidation(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    input.addEventListener('blur', function() {
        const cpf = input.value.replace(/\D/g, '');
        if (cpf.length === 0) {
            setFieldFeedback(input, null);
        } else if (cpf.length < 11) {
            setFieldFeedback(input, false, 'CPF incompleto');
        } else if (!validarCPF(cpf)) {
            setFieldFeedback(input, false, 'CPF inválido');
        } else {
            setFieldFeedback(input, true);
        }
    });
    
    input.addEventListener('input', function() {
        if (input.classList.contains('is-invalid') || input.classList.contains('is-valid')) {
            input.classList.remove('is-invalid', 'is-valid');
            const feedback = input.parentElement.querySelector('.invalid-feedback, .valid-feedback');
            if (feedback) feedback.remove();
        }
    });
}

// Validação em tempo real para Email
function setupEmailValidation(inputId) {
    const input = document.getElementById(inputId) || document.querySelector(`input[name="${inputId}"]`);
    if (!input) return;
    
    input.addEventListener('blur', function() {
        const email = input.value.trim();
        if (email.length === 0) {
            setFieldFeedback(input, null);
        } else if (!validarEmail(email)) {
            setFieldFeedback(input, false, 'E-mail inválido');
        } else {
            setFieldFeedback(input, true);
        }
    });
    
    input.addEventListener('input', function() {
        if (input.classList.contains('is-invalid') || input.classList.contains('is-valid')) {
            input.classList.remove('is-invalid', 'is-valid');
            const feedback = input.parentElement.querySelector('.invalid-feedback, .valid-feedback');
            if (feedback) feedback.remove();
        }
    });
}

// Validação em tempo real para Telefone
function setupTelefoneValidation(inputId) {
    const input = document.getElementById(inputId) || document.querySelector(`input[name="${inputId}"]`);
    if (!input) return;
    
    input.addEventListener('blur', function() {
        const telefone = input.value.trim();
        if (telefone.length === 0) {
            setFieldFeedback(input, null);
        } else if (!validarTelefone(telefone)) {
            setFieldFeedback(input, false, 'Telefone inválido. Use formato: (11) 98765-4321');
        } else {
            setFieldFeedback(input, true);
        }
    });
    
    input.addEventListener('input', function() {
        if (input.classList.contains('is-invalid') || input.classList.contains('is-valid')) {
            input.classList.remove('is-invalid', 'is-valid');
            const feedback = input.parentElement.querySelector('.invalid-feedback, .valid-feedback');
            if (feedback) feedback.remove();
        }
    });
}

// Validação em tempo real para URL
function setupURLValidation(inputId) {
    const input = document.getElementById(inputId) || document.querySelector(`input[name="${inputId}"]`);
    if (!input) return;
    
    input.addEventListener('blur', function() {
        const url = input.value.trim();
        if (url.length === 0) {
            setFieldFeedback(input, null);
        } else if (!validarURL(url)) {
            setFieldFeedback(input, false, 'URL inválida');
        } else {
            setFieldFeedback(input, true);
        }
    });
    
    input.addEventListener('input', function() {
        if (input.classList.contains('is-invalid') || input.classList.contains('is-valid')) {
            input.classList.remove('is-invalid', 'is-valid');
            const feedback = input.parentElement.querySelector('.invalid-feedback, .valid-feedback');
            if (feedback) feedback.remove();
        }
    });
}

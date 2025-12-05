// static/js/register.js

document.addEventListener("DOMContentLoaded", function () {
    // Toggle de visibilidade da senha
    const senhaInput = document.getElementById("senha");
    const toggleSenhaBtn = document.getElementById("toggleSenha");
    const senhaIcon = document.getElementById("senhaIcon");

    if (toggleSenhaBtn && senhaInput && senhaIcon) {
        toggleSenhaBtn.addEventListener("click", function () {
            const isPassword = senhaInput.type === "password";

            senhaInput.type = isPassword ? "text" : "password";

            // Atualiza o ícone baseado no estado atual
            const baseUrl = senhaIcon.src.substring(0, senhaIcon.src.lastIndexOf('/') + 1);
            senhaIcon.src = isPassword
                ? baseUrl + "hide.png"
                : baseUrl + "view.png";

            senhaIcon.alt = isPassword ? "ocultar senha" : "mostrar senha";
        });
    }

    // Máscaras de input usando Inputmask
    if (typeof Inputmask !== 'undefined') {
        // Máscara para CPF
        const cpfInput = document.getElementById("cpf");
        if (cpfInput) {
            Inputmask({"mask": "999.999.999-99"}).mask(cpfInput);
        }

        // Máscara para WhatsApp
        const whatsappInput = document.querySelector("input[name='whatsapp']");
        if (whatsappInput) {
            Inputmask({"mask": "(99) 99999-9999"}).mask(whatsappInput);
        }

        // Máscara para CRP
        const crpInput = document.getElementById("crp");
        if (crpInput) {
            Inputmask({"mask": "99/99999[9]", "greedy": false}).mask(crpInput);
        }
    }
});
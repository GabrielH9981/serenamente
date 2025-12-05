# JavaScript Files Organization

Este diretório contém todos os arquivos JavaScript separados dos templates HTML para manter um padrão mais organizado e facilitar a manutenção.

## Arquivos:

### `agenda.js`
- **Usado em**: `templates/agenda.html`
- **Função**: Gerencia a agenda mensal, edição/criação/exclusão de eventos
- **Dependências**: Bootstrap, variáveis window.AGENDA_CONFIG e window.eventsByDate

### `register.js`
- **Usado em**: `templates/register.html`
- **Função**: Lógica do formulário de cadastro (toggle senha, máscaras de input)
- **Dependências**: Inputmask

### `perfil.js`
- **Usado em**: `templates/perfil.html`
- **Função**: Lógica complexa do perfil (cropper, disponibilidade, ViaCEP, contadores)
- **Dependências**: Bootstrap, Cropper.js, Inputmask

### `perfil-publico.js`
- **Usado em**: `templates/perfil_publico.html`
- **Função**: Funções auxiliares para o perfil público (agendamento, slots)
- **Dependências**: Inputmask

### `backup.js`
- **Status**: Arquivo movido da pasta templates (era backup.js)
- **Função**: Código de backup/referência para agendamento
- **Nota**: Pode ser removido se não estiver sendo usado

## Padrão de Organização:

1. **JavaScript inline removido** dos templates HTML
2. **Scripts separados** por funcionalidade/página
3. **Configurações dinâmicas** mantidas inline nos templates (dados do servidor)
4. **Imports organizados** no final dos templates antes do `</body>`

## Como usar:

```html
<!-- No template HTML -->
<script src="{{ url_for('static', filename='js/nome-do-arquivo.js') }}"></script>
```

## Benefícios:

- ✅ Código mais limpo e organizado
- ✅ Facilita manutenção e debugging
- ✅ Reutilização de código
- ✅ Melhor cache do navegador
- ✅ Separação de responsabilidades
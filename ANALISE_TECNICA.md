# 📋 ANÁLISE TÉCNICA - PLATAFORMA DE PSICÓLOGOS

## Status da Correção
- 🔴 Não iniciado
- 🟡 Em progresso
- ✅ Concluído

---

## 🔴 CRÍTICO - SEGURANÇA

### 1. CREDENCIAIS EXPOSTAS NO .ENV ✅
**Status:** Resolvido (não commitado no Git)
- ✅ Arquivo `.env` não está no repositório
- ⚠️ Verificar se `.env` está no `.gitignore`

### 2. SECRET_KEY FRACA ✅
**Status:** CONCLUÍDO
**Problema:** `SECRET_KEY=e_o_pi_ja_qui_nho` é extremamente fraca e previsível
**Risco:** Session hijacking, CSRF attacks
**Solução Aplicada:**
- ✅ Gerada SECRET_KEY forte com 64 caracteres hexadecimais (256 bits)
- ✅ Removido fallback inseguro do código
- ✅ Aplicação agora falha se SECRET_KEY não estiver configurada
- ✅ Script `generate_keys.py` criado para gerar novas chaves

### 3. CREDENCIAIS DE ADMIN EM TEXTO PLANO ✅
**Status:** CONCLUÍDO
**Problema:** `ADMIN_USER=dok4_` e `ADMIN_PASS=nhamnham` são fracas e sem hash
**Risco:** Acesso não autorizado ao painel admin
**Solução Aplicada:**
- ✅ Implementado bcrypt para hash de senhas
- ✅ Senha do admin agora é validada com bcrypt.checkpw()
- ✅ Hash armazenado em ADMIN_PASS_HASH no .env
- ✅ Script `generate_admin_hash.py` criado para gerar hash
- ⚠️ Recomendação: Trocar senha 'nhamnham' por uma forte (use generate_keys.py)

### 4. SQL INJECTION PARCIALMENTE MITIGADO ✅
**Status:** CONCLUÍDO
**Problema:** Concatenação de strings em algumas queries
**Risco:** SQL Injection em campos específicos
**Solução Aplicada:**
- ✅ Revisadas todas as ~50+ queries do projeto
- ✅ Confirmado uso de prepared statements em 100% das queries
- ✅ Adicionada validação de tipos para parâmetros numéricos (min_v, max_v)
- ✅ Adicionada validação para parâmetro 'page' com try/except
- ✅ Todas as entradas de usuário agora são validadas antes de uso em queries
- ✅ Documento `SQL_INJECTION_FIXES.md` criado com detalhes

### 5. FALTA DE RATE LIMITING ✅
**Status:** CONCLUÍDO
**Problema:** Rotas de login/registro sem proteção contra brute force
**Risco:** Ataques automatizados, DDoS
**Solução Aplicada:**
- ✅ Implementado Flask-Limiter
- ✅ Limite global: 200 requisições/dia, 50/hora
- ✅ Login: 5 tentativas por minuto
- ✅ Registro: 3 cadastros por hora
- ✅ Admin login: 3 tentativas por minuto
- ⚠️ Nota: Usando memória (memory://). Para produção, considere Redis

### 6. TOKENS GOOGLE CALENDAR SEM CRIPTOGRAFIA ✅
**Status:** CONCLUÍDO (Infraestrutura pronta)
**Problema:** Tokens salvos em texto plano no banco
**Risco:** Vazamento de acesso às agendas dos psicólogos
**Solução Aplicada:**
- ✅ Criado módulo `utils/encryption.py` com Fernet
- ✅ Funções `encrypt_token()` e `decrypt_token()` implementadas
- ✅ ENCRYPTION_KEY gerada e adicionada ao .env
- ✅ Script `generate_keys.py` atualizado para gerar chave Fernet válida
- ⚠️ Nota: Infraestrutura pronta. Para aplicar nos tokens existentes:
  1. Criar migration para criptografar tokens atuais
  2. Atualizar ferramentas.py para usar encrypt/decrypt
  3. Atualizar psicologos.py e perfil.py para descriptografar ao ler

### 7. FALTA DE VALIDAÇÃO DE INPUT ✅
**Status:** CONCLUÍDO E APLICADO (Backend + Frontend)
**Problema:** URLs, telefones e outros campos sem validação adequada
**Risco:** XSS, injeção de dados maliciosos
**Solução Aplicada:**
- ✅ **Backend (Python):**
  - Adicionadas bibliotecas: email-validator, phonenumbers
  - `validar_email()` - Valida e normaliza emails
  - `validar_telefone()` - Valida e formata telefones (formato E164)
  - `validar_url()` - Valida URLs e adiciona https:// se necessário
  - `sanitizar_texto()` - Remove caracteres perigosos
  - `validar_cpf()` - Já existia, mantido
- ✅ **Frontend (JavaScript):**
  - Criado módulo `validators.js` reutilizável
  - Validação em tempo real com feedback visual (verde/vermelho)
  - Máscaras automáticas: CPF, Telefone, CRP
  - Atributos HTML5: type, minlength, maxlength, required, placeholder
  - Mensagens de erro claras e específicas
- ✅ **APLICADO EM:**
  - **auth.py**: Registro (email, CPF, telefone, nome, CRP)
  - **auth.py**: Login (email)
  - **auth.py**: Completar cadastro (CPF, telefone, nome, CRP)
  - **auth.py**: Alterar email (email)
  - **perfil.py**: Atualização de perfil (bio, website, telefone, endereço, redes sociais)
  - **Templates**: register.html, login.html, completar_cadastro.html
- ✅ Teste backend executado com sucesso (test_validacoes_aplicadas.py)
- ✅ Documentação: VALIDACOES_FRONTEND.md

### 8. CORS NÃO CONFIGURADO ✅
**Status:** CONCLUÍDO
**Problema:** Sem configuração de CORS
**Risco:** Requisições de origens não autorizadas
**Solução Aplicada:**
- ✅ Implementado Flask-CORS
- ✅ Produção: Apenas origem específica (ALLOWED_ORIGIN no .env)
- ✅ Desenvolvimento: localhost:5000 e 127.0.0.1:5000
- ✅ Credentials habilitados para cookies/sessões

### 9. FALTA DE HTTPS ENFORCEMENT ✅
**Status:** CONCLUÍDO
**Problema:** Cookies sem flags Secure/HttpOnly/SameSite
**Risco:** Session hijacking, CSRF
**Solução Aplicada:**
- ✅ SESSION_COOKIE_SECURE = True (produção)
- ✅ SESSION_COOKIE_HTTPONLY = True (sempre)
- ✅ SESSION_COOKIE_SAMESITE = 'Lax'
- ✅ PERMANENT_SESSION_LIFETIME = 86400 (24h)
- ✅ Debug mode desabilitado em produção

### 10. EXPOSIÇÃO DE INFORMAÇÕES SENSÍVEIS ✅
**Status:** CONCLUÍDO
**Problema:** Prints de debug com tokens em produção
**Risco:** Vazamento de informações em logs
**Solução Aplicada:**
- ✅ Criado módulo `utils/logger.py` com logging estruturado
- ✅ Rotação de logs (10MB, 5 backups)
- ✅ Logs separados: app.log e error.log
- ✅ Console apenas em desenvolvimento
- ✅ Substituídos prints críticos em app.py e auth.py
- ⚠️ Nota: Prints em scripts utilitários (generate_keys.py, test_*.py) mantidos (são ferramentas CLI)

---

## 🟠 ALTO - ESTRUTURA E ARQUITETURA

### 11. FALTA DE SEPARAÇÃO DE CONFIGURAÇÕES 🔴
**Problema:** Configurações hardcoded no código
**Solução:**
- Criar `config.py` com classes (Development, Production, Testing)
- Centralizar todas as configurações
- Usar factory pattern para criar app

### 12. AUSÊNCIA DE MIGRATIONS 🔴
**Problema:** Sem sistema de versionamento do schema
**Solução:**
- Implementar Flask-Migrate (Alembic)
- Criar migrations para schema atual
- Versionar mudanças no banco

### 13. CONEXÕES DE BANCO NÃO POOLED 🔴
**Problema:** Cada requisição abre/fecha conexão
**Solução:**
- Implementar connection pooling
- Usar SQLAlchemy ou mysql.connector.pooling
- Configurar pool size adequado

### 14. FALTA DE TRATAMENTO DE ERROS CENTRALIZADO 🔴
**Problema:** Try/except espalhados sem padrão
**Solução:**
- Criar error handlers globais
- Padronizar respostas de erro
- Logar erros adequadamente

### 15. AUSÊNCIA DE LOGGING ESTRUTURADO 🔴
**Problema:** Uso de `print()` ao invés de logging
**Solução:**
- Implementar logging com níveis (DEBUG, INFO, WARNING, ERROR)
- Usar formatação estruturada (JSON)
- Configurar rotação de logs

### 16. CÓDIGO DUPLICADO 🔴
**Problema:** Lógica repetida em múltiplos arquivos
**Locais:**
- Refresh de tokens Google (ferramentas.py, psicologos.py, perfil.py)
- Geração de slots de agenda (perfil.py, psicologos.py)
- Validação de scheduling_mode (múltiplos lugares)
**Solução:**
- Criar módulo `services/` com funções reutilizáveis
- Extrair lógica comum para helpers
- Aplicar DRY (Don't Repeat Yourself)

### 17. FALTA DE TESTES 🔴
**Problema:** Nenhum teste unitário ou de integração
**Solução:**
- Implementar pytest
- Criar testes unitários para funções críticas
- Testes de integração para fluxos principais
- Configurar CI/CD com testes

### 18. MISTURA DE RESPONSABILIDADES 🔴
**Problema:** Routes fazendo queries diretas ao banco
**Solução:**
- Criar camada de Models (SQLAlchemy)
- Criar camada de Services (lógica de negócio)
- Routes apenas para controle de requisições

### 19. FALTA DE DOCUMENTAÇÃO DE API 🔴
**Problema:** Endpoints JSON sem documentação
**Solução:**
- Implementar Swagger/OpenAPI
- Documentar todos os endpoints
- Incluir exemplos de request/response

---

## 🟡 MÉDIO - LEGIBILIDADE E MANUTENÇÃO

### 20. NOMES DE VARIÁVEIS INCONSISTENTES 🔴
**Problema:** Mistura português/inglês
**Solução:**
- Padronizar tudo em inglês
- Refatorar nomes de variáveis
- Atualizar banco de dados (migrations)

### 21. FUNÇÕES MUITO LONGAS 🔴
**Problema:** Funções com 150-200+ linhas
**Arquivos:** `perfil.py`, `psicologos.py`
**Solução:**
- Quebrar em funções menores (max 50 linhas)
- Extrair lógica para helpers
- Aplicar Single Responsibility Principle

### 22. MAGIC NUMBERS 🔴
**Problema:** Valores hardcoded sem contexto
**Exemplos:** `160`, `3000`, `200`, `21`, `7`
**Solução:**
- Criar constantes nomeadas
- Agrupar em arquivo `constants.py`
- Documentar significado de cada valor

### 23. COMENTÁRIOS DESNECESSÁRIOS 🔴
**Problema:** Código comentado não removido
**Solução:**
- Remover código comentado (usar Git para histórico)
- Remover comentários óbvios
- Manter apenas comentários que explicam "por quê"

### 24. FALTA DE TYPE HINTS 🔴
**Problema:** Funções sem anotações de tipo
**Solução:**
- Adicionar type hints em todas as funções
- Usar mypy para validação
- Melhorar autocomplete da IDE

### 25. IMPORTS DESORGANIZADOS 🔴
**Problema:** Imports no meio do código
**Solução:**
- Mover todos os imports para o topo
- Organizar: stdlib → third-party → local
- Usar isort para automatizar

### 26. STRINGS HARDCODED 🔴
**Problema:** Mensagens de erro/sucesso hardcoded
**Solução:**
- Criar arquivo de mensagens/constantes
- Preparar para i18n (internacionalização)
- Centralizar todas as strings

### 27. FALTA DE DOCSTRINGS 🔴
**Problema:** Poucas funções documentadas
**Solução:**
- Adicionar docstrings em todas as funções
- Seguir padrão Google/NumPy
- Documentar parâmetros e retornos

### 28. VALIDAÇÕES INCONSISTENTES 🔴
**Problema:** Validação de CPF não usada em todos os lugares
**Solução:**
- Centralizar validações em `validators.py`
- Aplicar em todos os pontos de entrada
- Criar decorators para validação

---

## 🟢 BAIXO - MELHORIAS GERAIS

### 29. TIMEZONE HARDCODED 🔴
**Problema:** `-3` e `America/Sao_Paulo` hardcoded
**Solução:**
- Configurar timezone em config
- Usar pytz/zoneinfo
- Permitir configuração por usuário (futuro)

### 30. FALTA DE PAGINAÇÃO EFICIENTE 🔴
**Problema:** Busca todos os perfis e pagina em memória
**Solução:**
- Implementar paginação no banco (LIMIT/OFFSET)
- Usar cursor-based pagination para melhor performance
- Adicionar índices no banco

### 31. SESSÃO ALEATÓRIA EM MEMÓRIA 🔴
**Problema:** `session[session_key]` pode crescer indefinidamente
**Solução:**
- Implementar TTL para sessões
- Usar Redis para sessões (produção)
- Limpar sessões antigas periodicamente

### 32. FALTA DE CACHE 🔴
**Problema:** Queries repetitivas sem cache
**Solução:**
- Implementar Flask-Caching
- Cachear abordagens, experiências, públicos
- Configurar TTL adequado

### 33. IMAGENS SEM OTIMIZAÇÃO 🔴
**Problema:** Resize fixo 300x300, sem compressão
**Solução:**
- Implementar múltiplos tamanhos (thumbnail, medium, large)
- Comprimir imagens (Pillow optimize)
- Usar WebP quando possível

### 34. FALTA DE MONITORAMENTO 🔴
**Problema:** Sem métricas ou alertas
**Solução:**
- Implementar APM (Sentry, New Relic)
- Monitorar performance de queries
- Alertas para erros críticos

### 35. DOCKER-COMPOSE COM SENHAS FRACAS 🔴
**Problema:** Senhas do MySQL hardcoded no docker-compose
**Solução:**
- Usar variáveis de ambiente
- Gerar senhas fortes
- Não commitar docker-compose com senhas

---

## 📊 PRIORIZAÇÃO DE CORREÇÕES

### Sprint 1 - Segurança Crítica (1-2 semanas)
- [ ] Item 2: SECRET_KEY forte
- [ ] Item 3: Admin credentials com hash
- [ ] Item 5: Rate limiting
- [ ] Item 7: Validação de inputs
- [ ] Item 9: Cookies seguros
- [ ] Item 10: Remover prints de debug

### Sprint 2 - Segurança Avançada (1-2 semanas)
- [ ] Item 4: Revisar SQL queries
- [ ] Item 6: Criptografar tokens Google
- [ ] Item 8: Configurar CORS

### Sprint 3 - Arquitetura (2-3 semanas)
- [ ] Item 11: Separar configurações
- [ ] Item 13: Connection pooling
- [ ] Item 14: Error handlers
- [ ] Item 15: Logging estruturado
- [ ] Item 16: Eliminar código duplicado

### Sprint 4 - Qualidade de Código (2-3 semanas)
- [ ] Item 18: Camada de Models/Services
- [ ] Item 21: Refatorar funções longas
- [ ] Item 22: Constantes nomeadas
- [ ] Item 24: Type hints
- [ ] Item 25: Organizar imports

### Sprint 5 - Infraestrutura (1-2 semanas)
- [ ] Item 12: Migrations
- [ ] Item 17: Testes unitários
- [ ] Item 30: Paginação eficiente
- [ ] Item 32: Cache

---

## 📝 NOTAS IMPORTANTES

1. **Backup antes de mudanças críticas**: Sempre fazer backup do banco antes de aplicar migrations
2. **Testar em ambiente de desenvolvimento**: Nunca aplicar mudanças direto em produção
3. **Documentar mudanças**: Manter changelog atualizado
4. **Code review**: Revisar código antes de merge
5. **Monitorar após deploy**: Acompanhar logs e métricas após cada mudança

---

## 🎯 MÉTRICAS DE SUCESSO

- [ ] 0 vulnerabilidades críticas (OWASP Top 10)
- [ ] 100% das queries com prepared statements
- [ ] Cobertura de testes > 70%
- [ ] Tempo de resposta < 200ms (p95)
- [ ] 0 credenciais hardcoded
- [ ] Logging estruturado em 100% do código
- [ ] Documentação de API completa

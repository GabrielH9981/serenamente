# Imagem base
FROM python:3.11-slim

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Diretório de trabalho
WORKDIR /app

# Instala dependências de sistema mínimas (se precisar de lib para mysqlclient, pillow etc)
RUN apt-get update && apt-get install -y \
    build-essential \
    libmariadb-dev-compat \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto
COPY . .

# Expõe a porta usada pelo gunicorn
EXPOSE 8000

# Comando de execução (ajusta o nome do módulo se necessário)
# Se o app Flask é "app" dentro de app.py => "app:app"
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]

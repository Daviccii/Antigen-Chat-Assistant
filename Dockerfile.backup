FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Frontend dependencies
COPY frontend/package.json frontend/package-lock.json* /app/frontend/
RUN apt-get update && apt-get install -y nodejs npm && \
    cd /app/frontend && npm install && \
    rm -rf /var/lib/apt/lists/*

# Application code
COPY . /app

# Build frontend
RUN cd /app/frontend && npm run build
RUN mkdir -p /app/backend/static && \
    cp -r /app/frontend/dist/* /app/backend/static/

EXPOSE 8000

CMD ["sh", "-c", "cd /app/backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

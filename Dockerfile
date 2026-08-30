FROM python:3.12-slim-bookworm

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Install frontend dependencies
COPY frontend/package.json frontend/package-lock.json* /app/frontend/
RUN cd /app/frontend && npm install

# Copy application
COPY . .

# Build frontend
RUN cd /app/frontend && npm run build

# Copy frontend into backend static directory
RUN mkdir -p /app/backend/static && \
    cp -r /app/frontend/dist/* /app/backend/static/

EXPOSE 8000

# Run migrations and start application
CMD ["sh", "-c", "cd /app/backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

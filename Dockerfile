FROM node:18-bullseye-slim

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set Python as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1
RUN update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

WORKDIR /app

# Copy requirements first for better caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend and install dependencies
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm install

# Copy application code
COPY . .

# Build frontend
RUN cd frontend && npm run build
RUN mkdir -p /app/backend/static
RUN cp -r frontend/dist/* /app/backend/static/

# Expose port
EXPOSE 8000

# Run database migrations and start the application
CMD cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
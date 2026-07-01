# Multi-stage: build the frontend, then run FastAPI serving the static bundle.

# --- Stage 1: build frontend ---
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend runtime ---
FROM python:3.12-slim AS backend
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Built SPA served by FastAPI; FRONTEND_DIST points here.
COPY --from=frontend /frontend/dist ./frontend_dist
ENV FRONTEND_DIST=/app/frontend_dist

EXPOSE 8000
# Single worker so in-memory rate limits stay coherent.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

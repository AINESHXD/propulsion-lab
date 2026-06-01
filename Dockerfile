# PropulsionLab production image.
# Small, dependency-light: the educational solvers are pure Python + NumPy/SciPy.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Application code only (tests, graph artifacts, venv are excluded via .dockerignore).
COPY app ./app

EXPOSE 8080

# Gunicorn supervising Uvicorn workers. 2 workers suits a small CPU-bound app;
# raise -w on larger machines. $PORT is provided by the platform (Fly sets it).
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8080} -w 2 --timeout 120 --access-logfile -"]

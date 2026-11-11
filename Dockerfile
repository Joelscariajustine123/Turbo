# Turbo Cab — one container: Django (website + API) + the built React app at /app/.

# ---- 1. Build the React app -------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build                      # -> /web/dist/app

# ---- 2. Python app ----------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
COPY --from=web /web/dist ./frontend/dist

# Collect static files at build time (a throwaway key is fine for this step).
RUN DJANGO_DEBUG=False DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

RUN useradd --create-home turbo && mkdir -p /srv/media && chown -R turbo /srv/media
USER turbo

# Render provides $PORT. Migrations run on start because the free plan has no pre-deploy step.
CMD python manage.py migrate --noinput \
 && python manage.py ensure_admin \
 && exec gunicorn turbo.wsgi:application \
      --bind 0.0.0.0:${PORT:-8000} \
      --workers ${WEB_CONCURRENCY:-2} \
      --timeout 60 \
      --access-logfile -

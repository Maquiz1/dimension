FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Static files are collected into the image and served by WhiteNoise.
RUN DJANGO_SECRET_KEY=build-only POSTGRES_DB=build POSTGRES_USER=build POSTGRES_PASSWORD=build \
    python manage.py collectstatic --noinput

# Run as an unprivileged user. media/ is a Docker volume and takes this ownership on first use.
RUN useradd --system --uid 1000 --home /app app \
    && mkdir -p media \
    && chown app:app media \
    && chmod +x docker/entrypoint.sh
USER app

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", \
     "--access-logfile", "-"]

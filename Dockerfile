# syntax = docker/dockerfile:1

ARG BASE_IMAGE=ghcr.io/dbca-wa/docker-apps-dev:ubuntu_2604_base_python_node

FROM ${BASE_IMAGE} AS builder

LABEL maintainer="asi@dbca.wa.gov.au"

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Australia/Perth \
    PRODUCTION_EMAIL=True \
    SECRET_KEY="ThisisNotRealKey" \
    SYSTEM_NAME_SHORT="apiary" \
    SITE_PREFIX='apiary-dev' \
    SITE_DOMAIN='dbca.wa.gov.au' \
    DEBUG=True

RUN apt-get update && apt-get upgrade -y && \
    apt-get install --no-install-recommends -y \
    g++ \
    gnupg \
    libgdal-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 5000 oim && useradd -g 5000 -u 5000 oim -s /bin/bash -d /app && \
    mkdir -p /app && chown -R oim:oim /app

WORKDIR /app
USER oim

ENV VIRTUAL_ENV=/app/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Install Python dependencies early to leverage caching
COPY --chown=oim:oim requirements.txt ./
RUN python3 -m venv $VIRTUAL_ENV && \
    $VIRTUAL_ENV/bin/pip install --upgrade pip && \
    $VIRTUAL_ENV/bin/pip install --no-cache-dir -r requirements.txt

# Inject the LibreOffice path into Python's site-packages (required for unoserver to work)
RUN SITE_PKG=$($VIRTUAL_ENV/bin/python -c "import site; print(site.getsitepackages()[0])") && \
    echo "/opt/libreoffice/program" > "$SITE_PKG/libreoffice.pth"

# Copy project files
COPY --chown=oim:oim gunicorn.ini.py manage.py python-cron ./
COPY --chown=oim:oim .git ./.git
COPY --chown=oim:oim disturbance ./disturbance

# Build frontend
RUN if [ -d /app/disturbance/frontend/disturbance ]; then \
    cd /app/disturbance/frontend/disturbance && npm ci --omit=dev && npm run build && rm -rf node_modules; \
    fi

# Collect static files and prepare DB indexes
RUN touch /app/.env && \
    $VIRTUAL_ENV/bin/python manage.py collectstatic --noinput && \
    $VIRTUAL_ENV/bin/python manage.py script_hash_indexes --skip-checks

# --- Runtime image ---
FROM ${BASE_IMAGE} AS runtime

ARG IMAGE_TAG
ARG IMAGE_NAME

LABEL maintainer="asi@dbca.wa.gov.au"

ENV DEBIAN_FRONTEND=noninteractive \
    DEBUG=True \
    TZ=Australia/Perth \
    PRODUCTION_EMAIL=False \
    SECRET_KEY="ThisisNotRealKey" \
    SITE_PREFIX='das-apiary' \
    SITE_DOMAIN='dbca.wa.gov.au' \
    ENABLE_SRI_CHECK=True \    
    CONTAINER_IMAGE_TAG=${IMAGE_TAG} \
    CONTAINER_IMAGE_NAME=${IMAGE_NAME}

RUN apt-get update && apt-get upgrade -y && \
    apt-get remove --purge -y binutils rust-coreutils git mtr patch vim 2>/dev/null || true && \
    apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 5000 oim && useradd -g 5000 -u 5000 oim -s /bin/bash -d /app && \
    mkdir -p /app/logs && chown -R oim:oim /app && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY startup.sh /
RUN chmod 755 /startup.sh

USER oim
WORKDIR /app

ENV VIRTUAL_ENV=/app/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Copy venv and built application from builder
COPY --from=builder --chown=oim:oim /app/venv /app/venv
COPY --from=builder --chown=oim:oim /app/disturbance /app/disturbance
COPY --from=builder --chown=oim:oim /app/staticfiles /app/staticfiles
COPY --from=builder --chown=oim:oim /app/gunicorn.ini.py /app/gunicorn.ini.py
COPY --from=builder --chown=oim:oim /app/manage.py /app/manage.py
COPY --from=builder --chown=oim:oim /app/.env /app/.env
COPY --from=builder --chown=oim:oim /app/python-cron /app/python-cron
COPY --from=builder --chown=oim:oim /app/sri-manifest.json /app/sri-manifest.json
COPY --from=builder --chown=oim:oim /app/sri-files /app/sri-files

# Cleanup
USER root

RUN wget -q https://raw.githubusercontent.com/dbca-wa/wagov_utils/refs/heads/main/wagov_utils/bin/package_cleanup_2604.sh -O /tmp/package_cleanup_2604.sh || true
RUN chmod 755 /tmp/package_cleanup_2604.sh || true
RUN /tmp/package_cleanup_2604.sh || true
USER oim

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/"]
CMD ["/startup.sh"]

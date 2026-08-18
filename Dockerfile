FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ODOO_RC=/etc/odoo/odoo.conf

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        fonts-dejavu \
        fonts-freefont-ttf \
        libevent-dev \
        libffi-dev \
        libfreetype6-dev \
        libjpeg62-turbo-dev \
        libldap2-dev \
        libpq-dev \
        libsasl2-dev \
        libssl-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libxmlsec1-openssl \
        libxslt1-dev \
        libzip-dev \
        node-less \
        npm \
        postgresql-client \
        tzdata \
        wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/odoo
COPY requirements.txt setup.py MANIFEST.in /opt/odoo/
COPY odoo /opt/odoo/odoo
RUN pip install --no-cache-dir -r requirements.txt
COPY . /opt/odoo
COPY docker/odoo.conf /etc/odoo/odoo.conf
COPY docker/entrypoint.sh /usr/local/bin/odoo-entrypoint

RUN useradd --system --home-dir /var/lib/odoo --create-home --shell /usr/sbin/nologin odoo \
    && mkdir -p /var/lib/odoo /mnt/extra-addons /mnt/enterprise \
    && chown -R odoo:odoo /opt/odoo /etc/odoo /var/lib/odoo /mnt/extra-addons /mnt/enterprise \
    && chmod 0755 /usr/local/bin/odoo-entrypoint

USER odoo
EXPOSE 8069 8071 8072
ENTRYPOINT ["/usr/local/bin/odoo-entrypoint"]
CMD []

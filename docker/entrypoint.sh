#!/bin/sh
set -eu
sed "s|\${ODOO_ADMIN_PASSWORD}|$ODOO_ADMIN_PASSWORD|g; s|\${POSTGRES_USER}|$POSTGRES_USER|g; s|\${POSTGRES_PASSWORD}|$POSTGRES_PASSWORD|g; s|\${ZOOM_ACCOUNT_ID}|$ZOOM_ACCOUNT_ID|g; s|\${ZOOM_CLIENT_ID}|$ZOOM_CLIENT_ID|g; s|\${ZOOM_CLIENT_SECRET}|$ZOOM_CLIENT_SECRET|g; s|\${ZOOM_SECRET_TOKEN}|$ZOOM_SECRET_TOKEN|g; s|\${ZOOM_HOST_EMAIL}|$ZOOM_HOST_EMAIL|g" /etc/odoo/odoo.conf > /tmp/odoo.conf
exec python3 /opt/odoo/odoo-bin -c /tmp/odoo.conf "$@"

# Dilligence Odoo deployment

This repository is Odoo 19 Community source. The Compose stack builds the image
from this checkout and leaves `/mnt/enterprise` available for a licensed Odoo
Enterprise checkout later.

1. Copy `.env.example` to `.env` and use unique strong values for both passwords.
2. Set `ODOO_DOMAIN` to the DNS name that points to this server.
3. Put custom modules in `custom-addons/`; put the licensed Enterprise source in
   `enterprise/` when it is available. Do not commit Enterprise source.
4. Validate and start with:

   ```sh
   docker compose config
   docker compose up -d --build
   docker compose ps
   curl -fsS http://127.0.0.1:${ODOO_LOCAL_PORT:-18069}/web/health
   ```

The stack does not bind 80/443 and therefore does not interfere with the
server-wide nginx-proxy. It binds Odoo locally on port 18069 for diagnostics;
public traffic is expected through the existing `proxy_default` network.

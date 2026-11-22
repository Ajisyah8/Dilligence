from odoo import SUPERUSER_ID, api


INDONESIAN_EVENT_CONFIRMATION = '''<div style="margin:0;padding:24px 12px;background:#f3f5f6;font-family:Arial,Helvetica,sans-serif;color:#263238;">
  <div style="max-width:600px;margin:0 auto;padding:28px;background:#ffffff;border:1px solid #e1e7e9;border-radius:10px;">
    <p style="margin:0 0 18px;font-size:20px;font-weight:bold;color:#11687d;">Diligence Academy</p>
    <h1 style="margin:0 0 20px;font-size:24px;line-height:1.3;color:#17394a;">Pendaftaran berhasil</h1>
    <p>Halo <t t-out="object.name or 'Peserta'"/>,</p>
    <p>Pendaftaran Anda telah dikonfirmasi untuk acara <strong t-out="object.event_id.name or ''"/>.</p>
    <p><strong>Jadwal:</strong><br/>
      <t t-out="format_datetime(object.event_begin_date, tz='Asia/Jakarta', dt_format='EEEE, d MMMM yyyy, HH:mm')"/>
      <t t-if="object.event_end_date">–<t t-out="format_datetime(object.event_end_date, tz='Asia/Jakarta', dt_format='HH:mm')"/></t> WIB
    </p>
    <t t-if="object.event_id.event_url">
      <p style="margin:24px 0;">
        <a t-att-href="object.event_id.event_url" style="display:inline-block;padding:12px 20px;background:#11687d;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Gabung Zoom</a>
      </p>
      <p>Jika tombol tidak dapat dibuka, gunakan tautan berikut:<br/>
        <a t-att-href="object.event_id.event_url" t-out="object.event_id.event_url"/>
      </p>
    </t>
    <p>Terima kasih telah mendaftar. Sampai bertemu di acara!</p>
    <p style="margin:24px 0 0;">Salam,<br/><strong>Diligence Academy</strong></p>
  </div>
</div>'''


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref('event.event_subscription', raise_if_not_found=False)
    if not template:
        return

    # Set the Indonesian translation explicitly. This replaces the English
    # fallback and removes legacy relative image/calendar URLs that Gmail
    # cannot load reliably on mobile.
    cr.execute(
        "UPDATE mail_template SET body_html = jsonb_set(body_html, '{id_ID}', to_jsonb(%s::text), true), "
        "write_date = now() WHERE id = %s",
        (INDONESIAN_EVENT_CONFIRMATION, template.id),
    )
    template.invalidate_recordset(['body_html'])

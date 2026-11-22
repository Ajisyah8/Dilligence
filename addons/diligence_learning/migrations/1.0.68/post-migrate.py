from odoo import SUPERUSER_ID, api


TICKET_VIEW = '''<data inherit_id="event.event_report_template_full_page_ticket">
    <xpath expr="//h2[@t-field='event.name']" position="before">
        <img t-if="event.organizer_id.image_256 or event.company_id.logo" t-att-src="image_data_uri(event.organizer_id.image_256 or event.company_id.logo)"
             alt="Diligence Academy" style="display:block;max-width:110px;max-height:64px;margin-bottom:12px;"/>
    </xpath>
    <xpath expr="//div[hasclass('o_event_full_page_ticket_barcode_container')]//img[contains(@t-attf-src, '/report/barcode/QR/')][1]" position="attributes">
        <attribute name="t-attf-src">/diligence/event/qr/{{attendee.barcode if attendee and attendee.barcode else '12345678901234567890'}}?width=152&amp;height=152</attribute>
    </xpath>
</data>'''

CTA = '''<div data-diligence-event-registration-cta="1" style="text-align:center;margin:28px auto;">
  <a href="/event/3/register" style="display:inline-block;padding:14px 34px;border-radius:32px;background:#11687d;color:#fff;text-decoration:none;font-weight:700;font-size:17px;">Daftar Sekarang</a>
</div>'''


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute("SELECT COALESCE(description->>'id_ID', description->>'en_US', '') FROM event_event WHERE id = 3")
    row = cr.fetchone()
    if row and row[0]:
        description = row[0]
        if 'data-diligence-event-registration-cta' not in description:
            if '<h2' in description:
                description = description.replace('<h2', CTA + '<h2', 1)
            else:
                description = CTA + description
            if '</section>' in description:
                description = description.replace('</section>', CTA + '</section>', 1)
            else:
                description += CTA
            cr.execute(
                "UPDATE event_event SET description = jsonb_set(description, '{id_ID}', to_jsonb(%s::text), true), write_date = now() WHERE id = 3",
                (description,),
            )

    xmlid = env['ir.model.data'].sudo().search([
        ('module', '=', 'diligence_learning'),
        ('name', '=', 'event_report_template_ticket_images'),
    ], limit=1)
    if not xmlid:
        parent = env.ref('event.event_report_template_full_page_ticket', raise_if_not_found=False)
        if parent:
            view = env['ir.ui.view'].sudo().create({
                'name': 'event.report.ticket.images.diligence',
                'type': 'qweb',
                'inherit_id': parent.id,
                'arch_db': TICKET_VIEW,
                'active': True,
                'priority': 50,
            })
            env['ir.model.data'].sudo().create({
                'module': 'diligence_learning',
                'name': 'event_report_template_ticket_images',
                'model': 'ir.ui.view',
                'res_id': view.id,
                'noupdate': False,
            })
    elif xmlid.model == 'ir.ui.view':
        env['ir.ui.view'].sudo().browse(xmlid.res_id).write({'arch_db': TICKET_VIEW})

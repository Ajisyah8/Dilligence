from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill the new multi-segment relation from legacy contact fields."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Segment = env['diligence.contact.segment'].with_context(active_test=False)
    Partner = env['res.partner'].with_context(active_test=False)
    segments = {segment.code: segment for segment in Segment.search([])}

    for partner in Partner.search([]):
        segment_ids = partner.diligence_contact_segment_ids
        if partner.diligence_contact_segment_id:
            segment_ids |= partner.diligence_contact_segment_id
        if not segment_ids and partner.diligence_contact_segment:
            legacy_segment = segments.get(partner.diligence_contact_segment)
            if legacy_segment:
                segment_ids |= legacy_segment
        missing = segment_ids - partner.diligence_contact_segment_ids
        if missing:
            partner.write({
                'diligence_contact_segment_ids': [(4, segment.id) for segment in missing],
            })

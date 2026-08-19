import base64
import json
from datetime import timezone

import requests

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class DiligenceSession(models.Model):
    _name = 'diligence.session'
    _description = 'Diligence Learning Session'
    _order = 'start_datetime asc'

    name = fields.Char(required=True)
    package_id = fields.Many2one(
        'product.template', string='Package', required=True, ondelete='cascade',
        domain=[('diligence_package_type', '!=', False)],
    )
    session_type = fields.Selection([
        ('group', 'Group Zoom'),
        ('private', 'Private Zoom'),
        ('one_on_one', 'Private 1-on-1'),
        ('qna', 'Live Q&A'),
    ], required=True, default='group')
    start_datetime = fields.Datetime('Start', required=True)
    end_datetime = fields.Datetime('End', required=True)
    timezone = fields.Char(default='Asia/Jakarta')
    coach_id = fields.Many2one('res.users', string='Coach')
    meeting_url = fields.Char('Zoom / Meeting URL')
    zoom_meeting_id = fields.Char('Zoom Meeting ID', copy=False, readonly=True)
    zoom_password = fields.Char('Zoom Password', copy=False, readonly=True)
    zoom_start_url = fields.Char('Zoom Host Start URL', copy=False, readonly=True)
    zoom_created = fields.Boolean('Created in Zoom', copy=False, readonly=True)
    capacity = fields.Integer('Capacity', default=8)
    attendee_ids = fields.One2many('diligence.session.attendee', 'session_id', string='Attendees')
    attendee_count = fields.Integer('Registered', compute='_compute_seats')
    seats_available = fields.Integer('Seats Available', compute='_compute_seats')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True)
    notes = fields.Text('Notes')

    @api.depends('attendee_ids.state', 'capacity')
    def _compute_seats(self):
        for session in self:
            session.attendee_count = len(session.attendee_ids.filtered(lambda attendee: attendee.state != 'cancelled'))
            session.seats_available = max(session.capacity - session.attendee_count, 0) if session.capacity else 0

    @api.constrains('start_datetime', 'end_datetime', 'capacity')
    def _check_schedule(self):
        for session in self:
            if session.end_datetime <= session.start_datetime:
                raise ValidationError('Session end must be later than session start.')
            if session.capacity < 0:
                raise ValidationError('Session capacity cannot be negative.')

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_mark_done(self):
        self.write({'state': 'done'})

    def action_create_zoom_meeting(self):
        for session in self:
            session._create_zoom_meeting()
        return True

    def _create_zoom_meeting(self):
        self.ensure_one()
        account_id = tools.config.get('zoom_account_id')
        client_id = tools.config.get('zoom_client_id')
        client_secret = tools.config.get('zoom_client_secret')
        host_email = tools.config.get('zoom_host_email')
        if not all((account_id, client_id, client_secret, host_email)):
            raise ValidationError(_(
                'Zoom configuration is incomplete. Set zoom_account_id, zoom_client_id, '
                'zoom_client_secret, and zoom_host_email in odoo.conf.'
            ))

        try:
            token_response = requests.post(
                'https://zoom.us/oauth/token',
                params={'grant_type': 'account_credentials', 'account_id': account_id},
                headers={
                    'Authorization': 'Basic ' + base64.b64encode(
                        f'{client_id}:{client_secret}'.encode()
                    ).decode(),
                },
                timeout=20,
            )
            token_response.raise_for_status()
            access_token = token_response.json()['access_token']

            start = fields.Datetime.to_datetime(self.start_datetime).replace(tzinfo=timezone.utc)
            duration = max(round((self.end_datetime - self.start_datetime).total_seconds() / 60), 1)
            meeting_response = requests.post(
                f'https://api.zoom.us/v2/users/{host_email}/meetings',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                },
                data=json.dumps({
                    'topic': self.name,
                    'type': 2,
                    'start_time': start.isoformat().replace('+00:00', 'Z'),
                    'duration': duration,
                    'timezone': self.timezone or 'Asia/Jakarta',
                    'agenda': self.notes or '',
                    'settings': {
                        'waiting_room': True,
                        'join_before_host': False,
                        'mute_upon_entry': True,
                    },
                }),
                timeout=20,
            )
            meeting_response.raise_for_status()
            meeting = meeting_response.json()
        except (requests.RequestException, KeyError, ValueError) as error:
            raise ValidationError(_('Zoom could not create the meeting: %s') % error) from error

        self.write({
            'meeting_url': meeting.get('join_url'),
            'zoom_meeting_id': str(meeting.get('id') or ''),
            'zoom_password': meeting.get('password') or False,
            'zoom_start_url': meeting.get('start_url') or False,
            'zoom_created': True,
        })


class DiligenceSessionAttendee(models.Model):
    _name = 'diligence.session.attendee'
    _description = 'Diligence Session Attendee'
    _order = 'session_id, partner_id'

    session_id = fields.Many2one('diligence.session', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    sale_order_id = fields.Many2one('sale.order', ondelete='set null')
    state = fields.Selection([
        ('registered', 'Registered'),
        ('attended', 'Attended'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
    ], default='registered', required=True)
    notes = fields.Text()

    @api.constrains('session_id', 'state')
    def _check_session_capacity(self):
        for attendee in self.filtered(lambda record: record.state != 'cancelled'):
            session = attendee.session_id
            if session.capacity and len(session.attendee_ids.filtered(
                lambda record: record.state != 'cancelled'
            )) > session.capacity:
                raise ValidationError(
                    'This session is full. Increase the capacity or choose another session.'
                )

    _session_partner_unique = models.Constraint(
        'UNIQUE(session_id, partner_id)',
        'A learner can only be registered once per session.',
    )

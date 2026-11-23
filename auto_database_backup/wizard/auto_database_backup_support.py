# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import json
import logging
from urllib.parse import quote
import requests
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DB_PARAM_ENDPOINT = 'blue_support.endpoint_url'
DB_PARAM_TOKEN = 'blue_support.api_token'
DB_PARAM_WHATSAPP = 'blue_support.whatsapp_number'
DEFAULT_WHATSAPP = '551151924469'
SUPPORT_TIMEOUT = (5, 20)

_logger = logging.getLogger(__name__)


class AutoDatabaseBackupSupport(models.TransientModel):
    _name = 'auto.database.backup.support'
    _description = 'Automatic Database Backup Support'

    name = fields.Char(
        string='Customer Name',
        default=lambda self: self.env.user.name,
        help='Enter name')
    email = fields.Char(
        string='Email', required=True,
        default=lambda self: self.env.user.email,
        help='Enter your Email')
    phone = fields.Char(
        string='Phone',
        default=lambda self: self.env.user.partner_id.phone,
        help='Contact number for follow-up (optional).')
    subject = fields.Char(
        string='Subject', required=True,
        default='Automatic Database Backup Support',
        help='Short summary of the issue.')
    description = fields.Text(
        string='Description',
        help='Specify your problem in detail.')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        help='Attach files related to your problem.')
    support_type = fields.Selection([
        ('functional', 'Functional Support'),
        ('technical', 'Technical Support'),
    ], string='Support Type', default='technical', help='Select support type')
    category = fields.Selection([
        ('installation', 'Installation'),
        ('configuration', 'Configuration'),
        ('bug', 'Bug'),
        ('feature_request', 'Feature Request'),
        ('performance', 'Performance'),
        ('other', 'Other'),
    ], string='Category', default='bug', help='What kind of issue is this?')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Blocker'),
    ], string='Priority', default='2', help='How urgent is this issue?')
    show_payload = fields.Boolean(
        string='Show what will be sent',
        help='Preview the exact payload before submitting.')
    payload_preview = fields.Text(
        string='Payload preview',
        compute='_compute_payload_preview',
        help='Read-only JSON of what will be sent on Submit. '
             'Attachment bytes are redacted to keep the preview readable.')

    def _prepare_attachment_payload(self):
        payload = []
        for attachment in self.attachment_ids:
            if not attachment.datas:
                continue
            data = attachment.datas
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            payload.append({
                'data': data,
                'name': attachment.name,
            })
        return payload

    def _build_payload(self, redact_attachments=False):
        self.ensure_one()
        if redact_attachments:
            count = sum(
                1 for attachment in self.attachment_ids
                if attachment.datas)
            attachments_value = (
                _('%d attachment') % count if count == 1
                else _('%d attachments') % count
            )
        else:
            attachments_value = self._prepare_attachment_payload()
        return {
            'params': {
                'customer_name': self.name or '',
                'email': self.email or '',
                'phone': self.phone or '',
                'subject': self.subject or '',
                'description': self.description or '',
                'support_type': self.support_type or '',
                'category': dict(self._fields['category'].selection).get(
                    self.category, ''),
                'priority': dict(self._fields['priority'].selection).get(
                    self.priority, ''),
                'attachments': attachments_value,
            }
        }

    @api.depends('name', 'email', 'phone', 'subject', 'description',
                 'support_type', 'category', 'priority', 'attachment_ids',
                 'show_payload')
    def _compute_payload_preview(self):
        for record in self:
            if record.show_payload:
                record.payload_preview = json.dumps(
                    record._build_payload(redact_attachments=True),
                    indent=2,
                    ensure_ascii=False,
                )
            else:
                record.payload_preview = False

    def _submit_support_request(self):
        """helpdesk nativo -> endpoint first-party -> SMTP (em cadeia)."""
        self.ensure_one()
        env = self.env
        if 'helpdesk.team' in env:
            team = env['helpdesk.team'].sudo().search([], limit=1)
            if team:
                body = chr(10).join([
                    self.description or '',
                    '',
                    'Origem: Suporte do Backup Automatico (auto_database_backup)',
                ])
                ticket = env['helpdesk.ticket'].sudo().create({
                    'team_id': team.id,
                    'name': self.subject or 'Suporte backup',
                    'partner_id': env.user.partner_id.id,
                    'description': body,
                })
                if self.attachment_ids:
                    ticket.message_post(
                        body='',
                        attachment_ids=[(4, a.id) for a in self.attachment_ids])
                _logger.info('auto backup support: ticket id=%s', ticket.id)
                return {'result': {'message': 'success',
                                   'ticket_id': 'TCK-%s' % ticket.id}}
        get_param = env['ir.config_parameter'].sudo().get_param
        url = (get_param(DB_PARAM_ENDPOINT, '') or '').strip()
        token = (get_param(DB_PARAM_TOKEN, '') or '').strip()
        if url and token:
            response = requests.post(
                url,
                json=self._build_payload(),
                timeout=SUPPORT_TIMEOUT,
                headers={'Authorization': 'Bearer %s' % token},
            )
            response.raise_for_status()
            return response.json()
        to_addr = (get_param('blue_support.email', '')
                   or 'suporte@conexaoazul.com').strip()
        desc = (self.description or '').replace(chr(10), '<br/>')
        rows = [
            '<b>%s</b>: %s' % ('Cliente', self.name or ''),
            '<b>%s</b>: %s' % ('E-mail', self.email or ''),
            '<b>%s</b>: %s' % ('Assunto', self.subject or ''),
            '<br/><b>Descricao</b>:<br/>%s' % desc,
        ]
        mail = env['mail.mail'].sudo().create({
            'subject': self.subject or 'Suporte backup',
            'email_to': to_addr,
            'body_html': '<div>%s</div>' % '<br/>'.join(rows),
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })
        mail.send()
        _logger.info('auto backup support: smtp fallback mail.id=%s', mail.id)
        return {'result': {'message': 'success', 'ticket_id': 'MAIL-%s' % mail.id}}

    def confirm_button(self):
        self.ensure_one()
        try:
            response_status = self._submit_support_request()
        except requests.HTTPError as error:
            status_code = (
                error.response.status_code if error.response is not None else 0
            )
            _logger.exception(
                "Support submission rejected by server (HTTP %s)", status_code)
            if status_code == 413:
                raise ValidationError(_(
                    "Your attachments are too large. "
                    "Please reduce their size and try again."
                )) from None
            if status_code >= 500:
                raise ValidationError(_(
                    "The support service is having issues. "
                    "Please try again in a few minutes."
                )) from None
            raise ValidationError(_(
                "The ticket submission was rejected. "
                "Please check your inputs and try again."
            )) from None
        except (requests.ConnectionError, requests.Timeout):
            _logger.exception(
                "Support submission failed due to a network error")
            raise ValidationError(_(
                "Could not reach the support service. "
                "Please check your network and try again."
            )) from None
        except (json.JSONDecodeError, ValueError):
            _logger.exception(
                "Support service returned an invalid response")
            raise ValidationError(_(
                "The support service returned an unexpected response. "
                "Please try again later."
            )) from None

        if response_status.get('result', {}).get('message') == 'success':
            result = response_status.get('result', {})
            ticket_id = result.get('ticket_id') or ''
            lines = [_("Your Ticket Created Successfully"), '']
            if ticket_id:
                lines.append(_("Ticket Reference : %s") % ticket_id)
            lines.extend(
                ['', _("Save this reference to follow up with Cybrosys.")])
            message = '\n'.join(lines)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': message,
                    'type': 'success',
                    'sticky': True,
                    'className': 'o_auto_database_backup_ticket_notification',
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        raise ValidationError(
            _("The ticket submission did not go through. Please try again.")
        )

    def whatsapp_button(self):
        self.ensure_one()
        message = "{name}\n{email}\n{description}".format(
            name=self.name,
            email=self.email,
            description=self.description,
        )
        phone_number = ''.join(
            c for c in str(self.env['ir.config_parameter'].sudo().get_param(
                DB_PARAM_WHATSAPP, DEFAULT_WHATSAPP)) if c.isdigit())
        return {
            'type': 'ir.actions.act_url',
            'url': f"https://wa.me/{phone_number}?text={quote(message)}",
            'target': 'new',
            'res_id': self.id,
        }

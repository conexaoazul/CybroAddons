# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
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
##############################################################################
import json
import logging
import re
from urllib.parse import quote, urlsplit

import requests
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Keep the technical module name for upgrades, but never inherit its former
# third-party endpoint or token when using Conexao Azul-branded support.
SUPPORT_ENDPOINT_PARAM = 'blue_support.endpoint_url'
SUPPORT_API_TOKEN_PARAM = 'blue_support.api_token'
SUPPORT_TRACKING_URL_PARAM = 'blue_support.tracking_url'
SUPPORT_WHATSAPP_PARAM = 'blue_support.whatsapp_number'
DEFAULT_SUPPORT_WHATSAPP = '551151924469'
SUPPORT_ALLOWED_HOST = 'conexaoazul.com'
SUPPORT_TIMEOUT = (5, 20)  # (connect, read) seconds

# Conservative attachment limits; confirm with our own endpoint before enabling.
MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_SIZE = 3 * 1024 * 1024  # 3 MB per file
ALLOWED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
                      '.pdf', '.doc', '.docx')

_logger = logging.getLogger(__name__)


class ClientSupport(models.TransientModel):
    _name = 'client.support'
    _description = 'Client Support'

    name = fields.Char(
        string='Customer Name',
        default=lambda self: self.env.user.name,
        help='Enter name')
    email = fields.Char(
        string='Email', required=True, default=lambda self: self.env.user.email,
        help='Enter your Email')
    phone = fields.Char(
        string='Phone',
        default=lambda self: self.env.user.partner_id.phone,
        help='Contact number for follow-up (optional).')
    subject = fields.Char(
        string='Subject', required=True,
        help='Short summary of the issue.')
    description = fields.Text(
        string='Description',
        help='Specify your problem in detail.')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments',
                                      help='Images (PNG, JPG, GIF, WEBP, BMP), PDF or Word documents, '
                                           'up to 5 files of 3 MB each.')
    support_type = fields.Selection([
        ('functional', 'Functional Support'),
        ('technical', 'Technical Support'), ], string="Support Type",
        default="technical", help='Select support type')
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
    ], string='Priority', default='2',
        help='How urgent is this issue?')
    show_payload = fields.Boolean(
        string='Show what will be sent',
        help='Preview the exact data sent to Conexão Azul before submitting.')
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
            count = sum(1 for a in self.attachment_ids if a.datas)
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
                    indent=2, ensure_ascii=False,
                )
            else:
                record.payload_preview = False

    @api.model
    def _get_support_endpoint(self):
        """Only send to an explicitly configured first-party HTTPS endpoint."""
        endpoint = (self.env['ir.config_parameter'].sudo().get_param(
            SUPPORT_ENDPOINT_PARAM) or '').strip()
        if not endpoint:
            raise ValidationError(_(
                "Support ticket submission is not configured yet. "
                "Please use the WhatsApp button to contact Conexão Azul."))
        self._validate_support_url(endpoint)
        return endpoint

    @api.model
    def _validate_support_url(self, url):
        parts = urlsplit(url)
        host = (parts.hostname or '').lower()
        if (parts.scheme != 'https'
                or not (host == SUPPORT_ALLOWED_HOST
                        or host.endswith('.' + SUPPORT_ALLOWED_HOST))
                or parts.username or parts.password
                or parts.query or parts.fragment):
            raise ValidationError(_(
                "The support URL must use HTTPS and a Conexão Azul domain."))

    @api.model
    def _get_support_api_token(self):
        token = (self.env['ir.config_parameter'].sudo().get_param(
            SUPPORT_API_TOKEN_PARAM) or '').strip()
        if not token:
            raise ValidationError(_(
                "Support ticket authentication is not configured yet. "
                "Please use the WhatsApp button to contact Conexão Azul."))
        return token

    @api.model
    def _get_tracking_url(self):
        """Optional first-party tracking URL, not an inferred endpoint path."""
        url = (self.env['ir.config_parameter'].sudo().get_param(
            SUPPORT_TRACKING_URL_PARAM) or '').strip()
        if url:
            self._validate_support_url(url)
        return url

    def _check_attachments(self):
        """Refuse attachments the support server would reject."""
        attachments = self.attachment_ids.filtered('datas')
        if len(attachments) > MAX_ATTACHMENTS:
            raise ValidationError(_(
                "You can attach at most %s files.", MAX_ATTACHMENTS))
        for attachment in attachments:
            name = (attachment.name or '').lower()
            if not name.endswith(ALLOWED_EXTENSIONS):
                raise ValidationError(_(
                    "\"%s\" can't be sent: only images (PNG, JPG, GIF, WEBP, "
                    "BMP), PDF and Word documents can be attached.",
                    attachment.name))
            if attachment.file_size > MAX_ATTACHMENT_SIZE:
                raise ValidationError(_(
                    "\"%s\" is larger than 3 MB. Please reduce its size.",
                    attachment.name))

    def _submit_support_request(self):
        self.ensure_one()
        endpoint = self._get_support_endpoint()
        token = self._get_support_api_token()
        response = requests.post(
            endpoint,
            json=self._build_payload(),
            headers={'Authorization': 'Bearer %s' % token},
            timeout=SUPPORT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _helpdesk_support_team(self):
        """Time de helpdesk local (somente quando mode=local)."""
        get_param = self.env['ir.config_parameter'].sudo().get_param
        try:
            tid = int(get_param('blue_support.helpdesk_team_id', '0') or 0)
        except ValueError:
            tid = 0
        team = None
        if tid:
            team = self.env['helpdesk.team'].sudo().browse(tid).exists()
        return team or self.env['helpdesk.team'].sudo().search([], limit=1)

    def _submit_via_helpdesk(self):
        """Cria helpdesk.ticket no DB local (usado so pelo DB da Conexao Azul)."""
        if 'helpdesk.team' not in self.env:
            return None
        team = self._helpdesk_support_team()
        if not team:
            return None
        body = chr(10).join([
            self.description or '',
            '',
            'Origem: Assistente de Suporte Conexão Azul (blue_support_client)',
        ])
        ticket = self.env['helpdesk.ticket'].sudo().create({
            'team_id': team.id,
            'name': self.subject or 'Suporte via assistente',
            'partner_id': self.env.user.partner_id.id,
            'description': body,
        })
        if self.attachment_ids:
            ticket.message_post(
                body='',
                attachment_ids=[(4, a.id) for a in self.attachment_ids])
        _logger.info('blue support: helpdesk.ticket local id=%s criado', ticket.id)
        return 'TCK-%s' % ticket.id

    def _rpc_call(self, base, service, method, args):
        r = requests.post(
            base,
            json={'jsonrpc': '2.0', 'method': 'call',
                  'params': {'service': service, 'method': method,
                             'args': args}, 'id': 1},
            timeout=(5, 20),
            headers={'User-Agent': 'blue_support_client/1.0'})
        r.raise_for_status()
        data = r.json()
        if 'error' in data:
            raise RuntimeError(str(data['error']))
        return data.get('result')

    def _submit_via_rpc(self):
        """Camada 1 p/ clientes: JSON-RPC first-party no DB central da Conexao Azul."""
        get_param = self.env['ir.config_parameter'].sudo().get_param
        base = (get_param('blue_support.gateway_url', '')
                or 'https://data.conexaoazul.com/jsonrpc').strip()
        db = (get_param('blue_support.gateway_db', 'consultas') or '').strip()
        login = (get_param('blue_support.gateway_login', '') or '').strip()
        key = (get_param('blue_support.gateway_api_key', '') or '').strip()
        if not (login and key):
            return None
        uid = self._rpc_call(base, 'common', 'authenticate',
                             [db, login, key, {}])
        if not uid:
            _logger.warning('blue support: auth RPC falhou (login=%s)', login)
            return None
        teams = self._rpc_call(base, 'object', 'execute_kw',
                               [db, uid, key, 'helpdesk.team', 'search',
                                [[]], {'limit': 1}])
        if not teams:
            return None
        vals = {
            'team_id': teams[0],
            'name': (self.subject or 'Suporte via assistente')[:200],
            'description': chr(10).join([
                self.description or '',
                '',
                'Origem: assistente de suporte (%s)' % (self.env.cr.dbname),
            ]),
        }
        if self.email:
            part = self._rpc_call(base, 'object', 'execute_kw',
                                  [db, uid, key, 'res.partner', 'search_read',
                                   [[['email', '=', self.email]]],
                                   {'fields': ['id'], 'limit': 1}])
            if part:
                vals['partner_id'] = part[0]['id']
        tid = self._rpc_call(base, 'object', 'execute_kw',
                             [db, uid, key, 'helpdesk.ticket', 'create',
                              [vals]])
        # O ticket ja existe: falha em anexo nao pode cair no fallback SMTP
        # (duplicaria o chamado). ir.attachment.datas ja vem em base64.
        try:
            attachment_ids = []
            for attachment in self.attachment_ids:
                if not attachment.datas:
                    continue
                data = attachment.datas
                if isinstance(data, bytes):
                    data = data.decode()
                attachment_ids.append(self._rpc_call(
                    base, 'object', 'execute_kw',
                    [db, uid, key, 'ir.attachment', 'create', [{
                        'name': attachment.name,
                        'datas': data,
                        'mimetype': attachment.mimetype
                        or 'application/octet-stream',
                        'res_model': 'helpdesk.ticket',
                        'res_id': tid,
                    }]]))
            if attachment_ids:
                self._rpc_call(
                    base, 'object', 'execute_kw',
                    [db, uid, key, 'helpdesk.ticket', 'message_post',
                     [[tid]], {'body': 'Anexos enviados pelo assistente.',
                               'attachment_ids': attachment_ids}])
        except Exception:
            _logger.exception(
                'blue support: ticket TCK-%s criado, falha ao anexar', tid)
        _logger.info('blue support: ticket remoto TCK-%s criado', tid)
        return 'TCK-%s' % tid

    def _submit_via_smtp(self):
        """Fallback: e-mail para suporte@ (idealmente o alias do helpdesk)."""
        get_param = self.env['ir.config_parameter'].sudo().get_param
        to_addr = (get_param('blue_support.email', '')
                   or 'suporte@conexaoazul.com').strip()
        desc = (self.description or '').replace(chr(10), '<br/>')
        rows = [
            '<b>%s</b>: %s' % ('Cliente', self.name or ''),
            '<b>%s</b>: %s' % ('E-mail', self.email or ''),
            '<b>%s</b>: %s' % ('Telefone', self.phone or ''),
            '<b>%s</b>: %s' % ('Tipo', self.support_type or ''),
            '<b>%s</b>: %s' % ('Categoria', self.category or ''),
            '<b>%s</b>: %s' % ('Prioridade', self.priority or ''),
            '<br/><b>Descricao</b>:<br/>%s' % desc,
        ]
        mail = self.env['mail.mail'].sudo().create({
            'subject': self.subject or 'Suporte via assistente',
            'email_to': to_addr,
            'body_html': '<div>%s</div>' % '<br/>'.join(rows),
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })
        mail.send()
        _logger.info('blue support: fallback smtp mail.id=%s -> %s', mail.id, to_addr)
        return ''

    def _run_submission(self):
        """Executor generico de cadeia (reuso entre wizards):
        mode=local -> helpdesk nativo; senao RPC central; fallback SMTP.
        Retorna (canal, ref). Levanta ValidationError se todos falharem."""
        self.ensure_one()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        mode = (get_param('blue_support.mode', 'gateway') or 'gateway').strip()
        ticket_ref = ''
        channel = ''
        if mode == 'local':
            try:
                reference = self._submit_via_helpdesk()
            except Exception:
                _logger.exception('helpdesk local falhou; proximo canal')
                reference = None
            if reference:
                return 'helpdesk', reference
        else:
            try:
                reference = self._submit_via_rpc()
            except Exception:
                _logger.exception('RPC central falhou; proximo canal')
                reference = None
            if reference:
                return 'rpc', reference
        try:
            self._submit_via_smtp()
            return 'smtp', ''
        except Exception:
            _logger.exception('Fallback SMTP falhou')
            raise ValidationError(_(
                "Nao foi possivel abrir o ticket agora. "
                "Use o botao WhatsApp para falar com a Conexao Azul.")) from None

    def confirm_button(self):
        """mode=local -> helpdesk nativo; senao RPC central -> SMTP. Zap sempre nos botoes."""
        self.ensure_one()
        self._check_attachments()
        channel, ticket_ref = self._run_submission()
        lines = ['Sua solicitacao foi registrada.']
        if channel == 'helpdesk':
            lines.insert(0, 'Ticket criado no Helpdesk da Conexao Azul.')
        elif channel == 'rpc':
            lines.insert(0, 'Ticket criado no suporte central da Conexao Azul.')
        elif channel == 'smtp':
            lines.insert(0, 'Sua solicitacao foi enviada por e-mail ao suporte.')
        if ticket_ref:
            lines.append('Referencia: %s' % ticket_ref)
        track_url = self._get_tracking_url()
        message = chr(10).join(lines)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'links': ([{'label': track_url, 'url': track_url}]
                          if track_url else []),
                'type': 'success',
                'sticky': True,
                'className': 'o_cybrosys_ticket_notification',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def whatsapp_button(self):
        """Open a WhatsApp chat with the support details."""
        self.ensure_one()
        message = "{name}\n{email}\n{description}".format(
            name=self.name or '',
            email=self.email or '',
            description=self.description or '',
        )
        # wa.me requires the number in full international format with digits
        # only — no '+', spaces or dashes.
        raw_number = self.env['ir.config_parameter'].sudo().get_param(
            SUPPORT_WHATSAPP_PARAM) or DEFAULT_SUPPORT_WHATSAPP
        phone_number = re.sub(r'\D', '', raw_number)
        if not 10 <= len(phone_number) <= 15:
            raise ValidationError(_("Configure a valid support WhatsApp number."))
        return {
            'type': 'ir.actions.act_url',
            'url': f"https://wa.me/{phone_number}?text={quote(message, safe='')}",
            'target': 'new',
            'res_id': self.id,
        }

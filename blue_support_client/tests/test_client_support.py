import base64
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..wizard import client_support


@tagged('post_install', '-at_install')
class TestClientSupport(TransactionCase):

    def setUp(self):
        super().setUp()
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.set_param(client_support.SUPPORT_ENDPOINT_PARAM,
                              'https://api.conexaoazul.com/support/tickets')
        self.params.set_param(client_support.SUPPORT_API_TOKEN_PARAM,
                              'example-test-token')

    def _wizard(self, files=()):
        attachments = self.env['ir.attachment'].create([
            {'name': name, 'datas': base64.b64encode(raw)} for name, raw in files])
        return self.env['client.support'].create({
            'subject': 'Help', 'email': 'user@example.com',
            'attachment_ids': [(6, 0, attachments.ids)]})

    def _mock_post(self, result):
        response = MagicMock()
        response.json.return_value = {'result': result}
        return patch.object(client_support.requests, 'post', return_value=response)

    def test_bearer_token_sent(self):
        """Only our configured service receives the configured bearer token."""
        with self._mock_post({'message': 'success', 'ticket_id': 'CYB-1'}) as post:
            action = self._wizard().confirm_button()
        headers = post.call_args.kwargs['headers']
        self.assertEqual(headers, {'Authorization': 'Bearer example-test-token'})
        self.assertEqual(post.call_args.args[0],
                         'https://api.conexaoazul.com/support/tickets')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertFalse(action['params']['links'])

    def test_no_endpoint_fails_closed_and_ignores_legacy_parameter(self):
        self.params.set_param(client_support.SUPPORT_ENDPOINT_PARAM, '')
        self.params.set_param('blue_support_client.endpoint_url',
                              'https://support.cybrosys.com/help/request')
        with self._mock_post({}) as post, self.assertRaises(ValidationError):
            self._wizard().confirm_button()
        post.assert_not_called()

    def test_third_party_endpoint_is_rejected_before_post(self):
        for url in (
            'https://support.cybrosys.com/help/request',
            'http://api.conexaoazul.com/support/tickets',
            'https://api.conexaoazul.com.attacker.example/tickets',
        ):
            self.params.set_param(client_support.SUPPORT_ENDPOINT_PARAM, url)
            with self._mock_post({}) as post, self.assertRaises(ValidationError):
                self._wizard().confirm_button()
            post.assert_not_called()

    def test_missing_authentication_is_rejected_before_post(self):
        self.params.set_param(client_support.SUPPORT_API_TOKEN_PARAM, '')
        with self._mock_post({}) as post, self.assertRaises(ValidationError):
            self._wizard().confirm_button()
        post.assert_not_called()

    def test_whatsapp_uses_configured_support_number(self):
        self.params.set_param(client_support.SUPPORT_WHATSAPP_PARAM,
                              '+55 (11) 5192-4469')
        action = self._wizard().whatsapp_button()
        self.assertTrue(action['url'].startswith(
            'https://wa.me/551151924469?text='))
        self.assertIn('user%40example.com', action['url'])

    def test_attachments_checked_before_sending(self):
        """Disallowed types, oversized files and too many files never reach the server."""
        cases = [
            [('drawing.svg', b'<svg/>')],
            [('big.pdf', b'%PDF' + b'0' * client_support.MAX_ATTACHMENT_SIZE)],
            [('f%s.pdf' % i, b'%PDF') for i in range(6)],
        ]
        for files in cases:
            with self._mock_post({}) as post, self.assertRaises(ValidationError):
                self._wizard(files).confirm_button()
            post.assert_not_called()

    def test_server_errors_explained(self):
        """Server error codes become clear messages."""
        expected = {
            'unauthorized': 'update the',
            'rate_limited': 'Too many support requests',
            'file_type_not_allowed': 'Only images',
        }
        for code, text in expected.items():
            with self._mock_post({'message': code}), self.assertRaises(ValidationError) as error:
                self._wizard().confirm_button()
            self.assertIn(text, str(error.exception))

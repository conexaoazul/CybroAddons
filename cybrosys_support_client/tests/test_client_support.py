import base64
from unittest.mock import MagicMock, mock_open, patch

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
        response.status_code = 200
        response.json.return_value = {'result': result}
        return patch.object(client_support.requests, 'post', return_value=response)

    def test_bearer_token_sent(self):
        """Only our configured service receives the configured bearer token."""
        wizard = self._wizard()
        with self._mock_post({'message': 'success', 'ticket_id': 'CYB-1'}) as post:
            action = wizard.confirm_button()
        headers = post.call_args.kwargs['headers']
        self.assertEqual(headers['Authorization'], 'Bearer example-test-token')
        self.assertEqual(headers['X-Idempotency-Key'], wizard.request_key)
        self.assertEqual(headers['X-Correlation-ID'], wizard.request_key)
        self.assertEqual(headers['Accept'], 'application/json')
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        self.assertEqual(post.call_args.args[0],
                         'https://api.conexaoazul.com/support/tickets')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertFalse(action['params']['links'])

    def test_no_endpoint_fails_closed_and_ignores_legacy_parameter(self):
        self.params.set_param(client_support.SUPPORT_ENDPOINT_PARAM, '')
        self.params.set_param('cybrosys_support_client.endpoint_url',
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


    def test_request_key_reused_across_retries(self):
        wizard = self._wizard()
        with self._mock_post({'message': 'success', 'ticket_id': 'CA-42'}) as post:
            wizard.confirm_button()
            wizard.confirm_button()
        self.assertEqual(post.call_count, 2)
        self.assertEqual(
            post.call_args_list[0].kwargs['headers']['X-Idempotency-Key'],
            post.call_args_list[1].kwargs['headers']['X-Idempotency-Key'])
        self.assertEqual(
            post.call_args_list[1].kwargs['headers']['X-Idempotency-Key'],
            wizard.request_key)

    def test_redirect_rejected_without_forwarding_bearer_or_payload(self):
        response = MagicMock()
        response.status_code = 307
        with patch.object(client_support.requests, 'post',
                          return_value=response) as post:
            with self.assertRaises(ValidationError):
                self._wizard().confirm_button()
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        response.raise_for_status.assert_not_called()

    def test_malformed_api_response_rejected(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [{'result': {'message': 'success'}}]
        with patch.object(client_support.requests, 'post',
                          return_value=response):
            with self.assertRaises(ValidationError):
                self._wizard().confirm_button()

    def test_mounted_secret_preferred_over_database_parameter(self):
        wizard = self._wizard()
        with (patch.dict(client_support.os.environ, {
                  client_support.SUPPORT_TOKEN_FILE_ENV:
                  '/run/secrets/blue_support_api_token'
              }),
              patch('builtins.open', mock_open(read_data='mounted-secret')),
              self._mock_post({'message': 'success', 'ticket_id': 'CA-43'}) as post):
            wizard.confirm_button()
        self.assertEqual(
            post.call_args.kwargs['headers']['Authorization'],
            'Bearer mounted-secret')

    def test_missing_mounted_secret_fails_closed_without_db_fallback(self):
        wizard = self._wizard()
        with (patch.dict(client_support.os.environ, {
                  client_support.SUPPORT_TOKEN_FILE_ENV:
                  '/run/secrets/blue_support_api_token'
              }),
              patch('builtins.open', side_effect=OSError('missing secret')),
              self._mock_post({}) as post):
            with self.assertRaises(ValidationError):
                wizard.confirm_button()
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
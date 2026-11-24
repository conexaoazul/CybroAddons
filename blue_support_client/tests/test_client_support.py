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
        # Existing RPC/SMTP remains the default. HTTP must be explicitly enabled.
        self.params.set_param('blue_support.mode', 'api')

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
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
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


    def test_api_idempotency_key_is_stable_per_wizard(self):
        wizard = self._wizard()
        with self._mock_post({'message': 'success', 'ticket_id': 'CA-42'}) as post:
            wizard.confirm_button()
            wizard.confirm_button()
        self.assertEqual(post.call_count, 2)
        keys = [call.kwargs['headers']['X-Idempotency-Key']
                for call in post.call_args_list]
        self.assertEqual(keys, [wizard.request_key, wizard.request_key])

    def test_redirect_and_invalid_receipt_fail_closed(self):
        wizard = self._wizard()
        redirect = MagicMock(status_code=307)
        with patch.object(client_support.requests, 'post', return_value=redirect) as post:
            with self.assertRaises(ValidationError):
                wizard.confirm_button()
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        for response in ({'result': {'message': 'success'}},
                         {'result': {'message': 'success', 'ticket_id': True}},
                         {'bad': 'shape'}):
            reply = MagicMock(status_code=200)
            reply.json.return_value = response
            with patch.object(client_support.requests, 'post', return_value=reply):
                with self.assertRaises(ValidationError):
                    wizard.confirm_button()

    def test_secret_file_preferred_and_missing_mount_fails_closed(self):
        wizard = self._wizard()
        with (patch.dict(client_support.os.environ, {
                  client_support.SUPPORT_TOKEN_FILE_ENV:
                  '/run/secrets/blue_support_api_token'}),
              patch('builtins.open', mock_open(read_data='mounted-secret')),
              self._mock_post({'message': 'success', 'ticket_id': 'CA-43'}) as post):
            wizard.confirm_button()
        self.assertEqual(
            post.call_args.kwargs['headers']['Authorization'],
            'Bearer mounted-secret')
        with (patch.dict(client_support.os.environ, {
                  client_support.SUPPORT_TOKEN_FILE_ENV:
                  '/run/secrets/blue_support_api_token'}),
              patch('builtins.open', side_effect=OSError('missing')),
              self._mock_post({}) as post):
            with self.assertRaises(ValidationError):
                wizard.confirm_button()
        post.assert_not_called()

    def test_tracking_url_validates_before_ticket_side_effect(self):
        self.params.set_param(client_support.SUPPORT_TRACKING_URL_PARAM,
                              'https://external.invalid/ticket/1')
        with self._mock_post({}) as post, self.assertRaises(ValidationError):
            self._wizard().confirm_button()
        post.assert_not_called()

    def test_api_transport_failure_does_not_fallback_to_smtp(self):
        with (patch.object(client_support.requests, 'post',
                           side_effect=client_support.requests.Timeout('timeout')),
              patch.object(client_support.ClientSupport, '_submit_via_smtp',
                           side_effect=AssertionError('SMTP should not be called')) as smtp):
            with self.assertRaises(ValidationError):
                self._wizard().confirm_button()
        smtp.assert_not_called()

    def test_existing_gateway_remains_available(self):
        self.params.set_param('blue_support.mode', 'gateway')
        with (patch.object(client_support.ClientSupport, '_submit_via_rpc',
                           return_value='TCK-42'),
              patch.object(client_support.requests, 'post') as post):
            action = self._wizard().confirm_button()
        post.assert_not_called()
        self.assertIn('TCK-42', action['params']['message'])

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
            'unauthorized': 'authentication is not configured',
            'rate_limited': 'Too many support requests',
            'file_type_not_allowed': 'Only images',
        }
        for code, text in expected.items():
            with self._mock_post({'message': code}), self.assertRaises(ValidationError) as error:
                self._wizard().confirm_button()
            self.assertIn(text, str(error.exception))

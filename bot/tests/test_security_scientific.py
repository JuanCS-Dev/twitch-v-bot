import unittest
from unittest.mock import MagicMock, patch
import json
import io
from bot.dashboard_server import HealthHandler

class TestSecurityScientific(unittest.TestCase):
    def setUp(self):
        self.mock_server = MagicMock()
        self.mock_request = MagicMock()
        self.mock_client_address = ('127.0.0.1', 12345)
        HealthHandler.log_message = MagicMock()

    def create_handler(self, path, headers=None, token_env="super_secret_token"):
        """Helper para criar um handler com estado controlado."""
        # Criamos o patch para o token global
        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", token_env):
            handler = HealthHandler.__new__(HealthHandler)
            handler.path = path
            handler.headers = headers or {}
            handler.client_address = self.mock_client_address
            handler.rfile = io.BytesIO()
            handler.wfile = io.BytesIO()
            handler._logger = MagicMock()
            return handler

    def test_scientific_auth_denial_missing_token_env(self):
        """CIENTÍFICO: Se o token não estiver no ambiente, o acesso DEVE ser negado (Hard Denial)."""
        handler = self.create_handler("/api/control-plane", token_env="")
        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", ""):
            self.assertFalse(handler._dashboard_authorized())

    def test_scientific_auth_denial_short_token_env(self):
        """CIENTÍFICO: Tokens com menos de 8 caracteres devem ser rejeitados por política de segurança."""
        handler = self.create_handler("/api/control-plane", token_env="1234567")
        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "1234567"):
            self.assertFalse(handler._dashboard_authorized())

    def test_scientific_auth_success_with_valid_token(self):
        """CIENTÍFICO: Com token válido e header correto, o acesso deve ser permitido."""
        token = "valid_long_token_123"
        headers = {"X-Byte-Admin-Token": token}
        handler = self.create_handler("/api/control-plane", headers=headers, token_env=token)
        
        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", token):
            with patch("bot.dashboard_server.is_dashboard_admin_authorized", return_value=True):
                self.assertTrue(handler._dashboard_authorized())

    def test_scientific_config_js_leak_prevention(self):
        """CIENTÍFICO: O endpoint config.js NÃO DEVE conter o token real em nenhuma circunstância."""
        from bot.dashboard_server_routes import handle_get_config_js
        
        mock_handler = MagicMock()
        with patch("bot.runtime_config.BYTE_DASHBOARD_ADMIN_TOKEN", "MY_SUPER_SECRET_TOKEN"):
            handle_get_config_js(mock_handler)
            
            args, kwargs = mock_handler._send_bytes.call_args
            payload = args[0].decode('utf-8')
            
            self.assertIn("adminToken: null", payload)
            self.assertNotIn("MY_SUPER_SECRET_TOKEN", payload)

    def test_scientific_query_param_auth_hmac(self):
        """CIENTÍFICO: Validar se o bypass via query param ?auth= ainda funciona com HMAC seguro."""
        token = "secure_token_for_query_param"
        path = f"/api/status?auth={token}"
        handler = self.create_handler(path, token_env=token)
        
        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", token):
            with patch("bot.dashboard_server.is_dashboard_admin_authorized", return_value=False):
                self.assertTrue(handler._dashboard_authorized())

if __name__ == "__main__":
    unittest.main()

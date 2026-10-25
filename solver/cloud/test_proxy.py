"""Boundary checks for the WSL API proxy: origin, ownership cookies and failures."""
import http.client
import io
import json
import threading
import unittest
from email.message import Message
from unittest.mock import patch
import app

class Response(io.BytesIO):
    code = 429
    def __init__(self):
        super().__init__(b'{"status":"error","reason":"daily limit"}')
        self.headers = Message()
        self.headers['Content-Type'] = 'application/json'
        self.headers['Set-Cookie'] = 'othello_session=abc; Secure; HttpOnly; SameSite=Lax; Path=/'

class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.backend = patch.object(app, 'API_BACKEND', 'https://owned-backend.example:10000')
        self.backend.start()
    def tearDown(self):
        self.backend.stop(); self.server.shutdown(); self.server.server_close(); self.thread.join()
    def request(self, origin=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Content-Type':'application/json', 'Cookie':'othello_session=private-cookie'}
        if origin: headers['Origin'] = origin
        connection.request('POST', '/api/solve', b'{"id":"test_request"}', headers)
        result = connection.getresponse(); raw = result.read(); connection.close()
        return result, raw
    def test_foreign_origin_rejected_before_backend(self):
        with patch.object(app.urllib.request, 'urlopen') as request:
            response, _ = self.request('https://foreign.example')
            self.assertEqual(response.status, 403); request.assert_not_called()
    def test_preserves_backend_status_owner_cookie_and_same_origin(self):
        with patch.object(app.urllib.request, 'urlopen', return_value=Response()) as request:
            response, raw = self.request(f'http://127.0.0.1:{self.server.server_port}')
            self.assertEqual(response.status, 429)
            self.assertIn('HttpOnly', response.getheader('Set-Cookie'))
            self.assertEqual(response.getheader('X-Othello-Compute'), 'wsl')
            upstream = request.call_args.args[0]
            self.assertEqual(upstream.get_header('Cookie'), 'othello_session=private-cookie')
            self.assertEqual(upstream.get_header('Origin'), app.API_BACKEND)
            self.assertEqual(upstream.full_url, app.API_BACKEND+'/api/solve')
            self.assertEqual(json.loads(raw)['reason'], 'daily limit')
    def test_backend_unavailable_is_not_resubmitted_elsewhere(self):
        with patch.object(app.urllib.request, 'urlopen', side_effect=TimeoutError), patch.object(app, 'reserve') as reserve:
            response, _ = self.request()
            self.assertEqual(response.status, 503); reserve.assert_not_called()

if __name__ == '__main__': unittest.main()

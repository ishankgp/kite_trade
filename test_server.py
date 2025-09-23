#!/usr/bin/env python3
"""
Simple test server to get your GitHub Codespace URL for Zerodha Kite app registration
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        if self.path.startswith('/callback'):
            # Parse query parameters (Zerodha will send request_token here)
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            
            html = f"""
            <html>
            <head><title>Kite Callback Test</title></head>
            <body>
                <h1>✅ Callback URL Working!</h1>
                <p><strong>Your Codespace URL:</strong> {self.headers.get('Host')}</p>
                <p><strong>Use this for Zerodha Kite app registration:</strong></p>
                <code>https://{self.headers.get('Host')}/callback</code>
                
                <h2>Query Parameters Received:</h2>
                <pre>{json.dumps(params, indent=2)}</pre>
                
                <p>If you see a <code>request_token</code> parameter above, 
                   your Zerodha authentication is working! 🎉</p>
            </body>
            </html>
            """
        else:
            html = f"""
            <html>
            <head><title>Kite Test Server</title></head>
            <body>
                <h1>🚀 GitHub Codespace Test Server</h1>
                <p><strong>Your Codespace URL:</strong> {self.headers.get('Host')}</p>
                
                <h2>For Zerodha Kite App Registration:</h2>
                <ul>
                    <li><strong>Redirect URL:</strong> <code>https://{self.headers.get('Host')}/callback</code></li>
                    <li><strong>Postback URL:</strong> <code>https://{self.headers.get('Host')}/postback</code> (optional)</li>
                </ul>
                
                <p><a href="/callback?test=true">Test callback endpoint</a></p>
            </body>
            </html>
            """
        
        self.wfile.write(html.encode())
    
    def do_POST(self):
        # Handle postback webhooks
        if self.path == '/postback':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            print(f"📡 Postback received: {post_data.decode()}")
            self.wfile.write(b'{"status": "ok"}')

if __name__ == '__main__':
    port = 5000
    server = HTTPServer(('0.0.0.0', port), TestHandler)
    print(f"🌐 Starting test server on port {port}")
    print(f"📝 Access your server to get the exact URLs for Zerodha registration")
    server.serve_forever()
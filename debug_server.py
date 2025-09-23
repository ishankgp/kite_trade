#!/usr/bin/env python3
"""
Enhanced server to debug Zerodha Kite 413 errors and handle large payloads
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedKiteHandler(BaseHTTPRequestHandler):
    def log_request_details(self):
        """Log detailed request information"""
        logger.info(f"🔍 Request Method: {self.command}")
        logger.info(f"🔍 Request Path: {self.path}")
        logger.info(f"🔍 Headers: {dict(self.headers)}")
        
        # Check content length
        content_length = int(self.headers.get('Content-Length', 0))
        logger.info(f"🔍 Content-Length: {content_length} bytes")
        
        if content_length > 1024 * 1024:  # 1MB
            logger.warning(f"⚠️  Large payload detected: {content_length / (1024*1024):.2f} MB")
    
    def do_GET(self):
        self.log_request_details()
        
        # Parse URL and query parameters
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        # Check if URL is too long
        if len(self.path) > 2048:
            logger.warning(f"⚠️  Long URL detected: {len(self.path)} characters")
        
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            if self.path.startswith('/callback'):
                html = self.generate_callback_page(params)
            elif self.path.startswith('/postback'):
                html = self.generate_postback_page()
            else:
                html = self.generate_home_page()
            
            self.wfile.write(html.encode('utf-8'))
            logger.info("✅ Response sent successfully")
            
        except Exception as e:
            logger.error(f"❌ Error handling GET request: {e}")
            self.send_error(500, f"Server error: {e}")
    
    def do_POST(self):
        self.log_request_details()
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Handle large payloads more gracefully
            if content_length > 10 * 1024 * 1024:  # 10MB limit
                logger.error(f"❌ Payload too large: {content_length} bytes")
                self.send_error(413, "Request Entity Too Large")
                return
            
            # Read data in chunks if it's large
            if content_length > 0:
                if content_length > 1024 * 1024:  # 1MB
                    logger.info("📥 Reading large payload in chunks...")
                    post_data = b''
                    remaining = content_length
                    chunk_size = 8192
                    
                    while remaining > 0:
                        chunk = self.rfile.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        post_data += chunk
                        remaining -= len(chunk)
                        logger.debug(f"📥 Read {len(chunk)} bytes, {remaining} remaining")
                else:
                    post_data = self.rfile.read(content_length)
                
                logger.info(f"📥 Received {len(post_data)} bytes")
                
                # Try to decode and log the data
                try:
                    decoded_data = post_data.decode('utf-8')
                    if len(decoded_data) < 1000:  # Only log if not too large
                        logger.info(f"📄 POST Data: {decoded_data}")
                    else:
                        logger.info(f"📄 POST Data (truncated): {decoded_data[:500]}...")
                        
                    # Try to parse as JSON
                    if self.headers.get('Content-Type', '').startswith('application/json'):
                        json_data = json.loads(decoded_data)
                        logger.info(f"📊 Parsed JSON keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict'}")
                        
                except UnicodeDecodeError:
                    logger.info("📄 POST Data: Binary data (cannot decode as UTF-8)")
                except json.JSONDecodeError as e:
                    logger.info(f"📄 POST Data: Not valid JSON - {e}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {"status": "success", "message": "Data received successfully"}
            self.wfile.write(json.dumps(response).encode())
            logger.info("✅ POST response sent successfully")
            
        except Exception as e:
            logger.error(f"❌ Error handling POST request: {e}")
            self.send_error(500, f"Server error: {e}")
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def generate_home_page(self):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kite Debug Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .info {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .warning {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                code {{ background: #f1f1f1; padding: 2px 5px; border-radius: 3px; }}
                .url {{ font-family: monospace; background: #f8f9fa; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>🔧 Kite Debug Server</h1>
            <p><strong>Your Codespace URL:</strong> {self.headers.get('Host')}</p>
            
            <div class="info">
                <h2>📝 For Zerodha Kite App Registration:</h2>
                <p><strong>Redirect URL:</strong></p>
                <div class="url">https://{self.headers.get('Host')}/callback</div>
                
                <p><strong>Postback URL (optional):</strong></p>
                <div class="url">https://{self.headers.get('Host')}/postback</div>
            </div>
            
            <div class="warning">
                <h3>🚨 Troubleshooting 413 Error:</h3>
                <ul>
                    <li>Check server logs in the terminal for payload size details</li>
                    <li>Ensure your redirect URL exactly matches what you registered</li>
                    <li>Verify no extra parameters are being added to URLs</li>
                    <li>Check if postback webhooks are sending large data</li>
                </ul>
            </div>
            
            <h3>🧪 Test Endpoints:</h3>
            <ul>
                <li><a href="/callback?test=true">Test callback endpoint</a></li>
                <li><a href="/postback">Test postback endpoint</a></li>
            </ul>
        </body>
        </html>
        """
    
    def generate_callback_page(self, params):
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Kite Callback - Debug</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>✅ Callback URL Working!</h1>
            <p><strong>Your Codespace URL:</strong> {self.headers.get('Host')}</p>
            
            <h2>📊 Query Parameters Received:</h2>
            <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px;">{json.dumps(params, indent=2)}</pre>
            
            <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0;">
                {'<p>🎉 <strong>SUCCESS!</strong> Found request_token - Zerodha authentication is working!</p>' if 'request_token' in params else '<p>⏳ Waiting for request_token from Zerodha...</p>'}
            </div>
            
            <h3>📏 URL Length Analysis:</h3>
            <p>Total URL length: {len(self.path)} characters</p>
            {'<p style="color: orange;">⚠️ URL is quite long - this might cause issues with some servers</p>' if len(self.path) > 1000 else '<p style="color: green;">✅ URL length is acceptable</p>'}
        </body>
        </html>
        """
    
    def generate_postback_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Kite Postback - Debug</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>📡 Postback Endpoint</h1>
            <p>This endpoint receives webhook notifications from Zerodha Kite.</p>
            <p>Check the server logs in your terminal to see incoming webhook data.</p>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 5px;">
                <strong>Note:</strong> Large webhook payloads might cause 413 errors. 
                Check the terminal logs for payload size information.
            </div>
        </body>
        </html>
        """

if __name__ == '__main__':
    port = 5000
    server = HTTPServer(('0.0.0.0', port), EnhancedKiteHandler)
    
    print("🔧 Enhanced Kite Debug Server Starting...")
    print(f"🌐 Server running on port {port}")
    print("📊 Detailed logging enabled - check terminal for request details")
    print("🚨 This server will help diagnose 413 errors")
    print("-" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        server.shutdown()
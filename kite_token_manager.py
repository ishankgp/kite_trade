#!/usr/bin/env python3
"""
Kite Token Manager - Handles Daily Token Renewal
===============================================

This script manages Kite authentication tokens properly:
- Stores access tokens securely
- Automatically handles token expiration
- Provides seamless re-authentication
- Saves tokens for reuse within the same day

Key Points:
- Request tokens are single-use only
- Access tokens expire daily at market close (~3:30 PM IST)
- You need to re-authenticate daily for live trading
"""

import os
import json
import time
import pickle
from datetime import datetime, timezone, timedelta
from kiteconnect import KiteConnect
import requests
from env_loader import get_kite_config

# Load credentials from environment (.env) instead of hard-coding
_cfg = get_kite_config()
API_KEY = _cfg['api_key']
REDIRECT_URL = _cfg['redirect_url']
API_SECRET_DEFAULT = _cfg['api_secret']

# File paths for storing tokens
ACCESS_TOKEN_FILE = "/workspaces/kite_trade/access_token.json"
SESSION_DATA_FILE = "/workspaces/kite_trade/session_data.pkl"

class KiteTokenManager:
    def __init__(self, api_key, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = KiteConnect(api_key=api_key)
        self.access_token = None
        self.user_id = None
        self.token_expiry = None
        
    def load_saved_session(self):
        """Load previously saved access token if still valid"""
        try:
            if os.path.exists(ACCESS_TOKEN_FILE):
                with open(ACCESS_TOKEN_FILE, 'r') as f:
                    data = json.load(f)
                
                # Check if token is still valid (not expired)
                expiry_time = datetime.fromisoformat(data.get('expiry', ''))
                current_time = datetime.now(timezone.utc)
                
                if current_time < expiry_time:
                    self.access_token = data['access_token']
                    self.user_id = data['user_id']
                    self.token_expiry = expiry_time
                    self.kite.set_access_token(self.access_token)
                    
                    print(f"✅ Loaded saved access token for user: {self.user_id}")
                    print(f"🕐 Token expires at: {expiry_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    return True
                else:
                    print("⏰ Saved access token has expired")
                    self.clear_saved_session()
                    return False
            
        except Exception as e:
            print(f"⚠️  Error loading saved session: {e}")
            return False
        
        return False
    
    def save_session(self, access_token, user_id):
        """Save access token with expiry information"""
        try:
            # Kite tokens typically expire at 3:30 PM IST next day
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            tomorrow = datetime.now(ist_tz) + timedelta(days=1)
            expiry_time = tomorrow.replace(hour=15, minute=30, second=0, microsecond=0)
            
            # Convert to UTC for storage
            expiry_utc = expiry_time.astimezone(timezone.utc)
            
            session_data = {
                'access_token': access_token,
                'user_id': user_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'expiry': expiry_utc.isoformat(),
                'api_key': self.api_key
            }
            
            with open(ACCESS_TOKEN_FILE, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            print(f"💾 Session saved. Expires at: {expiry_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving session: {e}")
            return False
    
    def clear_saved_session(self):
        """Clear saved session files"""
        for file_path in [ACCESS_TOKEN_FILE, SESSION_DATA_FILE]:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Removed {file_path}")
    
    def is_token_valid(self):
        """Check if current access token is valid by making a test API call"""
        if not self.access_token:
            return False
        
        try:
            # Test with a simple API call
            self.kite.profile()
            return True
        except Exception as e:
            print(f"❌ Token validation failed: {e}")
            return False
    
    def authenticate_fresh(self, api_secret):
        """Perform fresh authentication with request token"""
        if not api_secret:
            print("❌ API secret is required for authentication")
            return False
        
        self.api_secret = api_secret
        
        # Generate login URL
        login_url = self.kite.login_url()
        print("\n🔐 FRESH AUTHENTICATION REQUIRED")
        print("=" * 50)
        print(f"🔗 Login URL: {login_url}")
        print("\n📋 Instructions:")
        print("1. Click the URL above (or copy-paste in browser)")
        print("2. Login with your Zerodha credentials")
        print("3. You'll be redirected to your callback URL")
        print("4. Copy the 'request_token' from the URL")
        print("5. Paste it below")
        print()
        
        # Get request token from user
        request_token = input("🎫 Enter request_token: ").strip()
        
        if not request_token:
            print("❌ No request token provided")
            return False
        
        try:
            # Exchange request token for access token
            data = self.kite.generate_session(request_token, api_secret)
            
            self.access_token = data["access_token"]
            self.user_id = data["user_id"]
            
            # Set access token for subsequent calls
            self.kite.set_access_token(self.access_token)
            
            # Save session for future use
            self.save_session(self.access_token, self.user_id)
            
            print(f"✅ Authentication successful!")
            print(f"👤 User ID: {self.user_id}")
            print(f"🔐 Access Token: {self.access_token[:20]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def ensure_authenticated(self, api_secret=None):
        """Ensure we have a valid access token, authenticate if needed"""
        
        # Try to load saved session first
        if self.load_saved_session():
            if self.is_token_valid():
                print("🎉 Using valid saved session")
                return True
            else:
                print("⚠️  Saved session is invalid, clearing...")
                self.clear_saved_session()
        
        # If no valid saved session, need fresh authentication
        print("🔄 Fresh authentication required...")
        
        if not api_secret:
            api_secret = input("🔒 Enter your API Secret: ").strip()
        
        return self.authenticate_fresh(api_secret)
    
    def get_session_status(self):
        """Get current session status"""
        status = {
            "has_access_token": bool(self.access_token),
            "user_id": self.user_id,
            "token_valid": self.is_token_valid() if self.access_token else False,
            "token_expiry": self.token_expiry.isoformat() if self.token_expiry else None
        }
        return status
    
    def test_api_calls(self):
        """Test various API calls to verify token works"""
        if not self.access_token:
            print("❌ No access token available")
            return False
        
        print("\n🧪 Testing API Calls...")
        
        tests = [
            ("Profile", lambda: self.kite.profile()),
            ("Margins", lambda: self.kite.margins()),
            ("Holdings", lambda: self.kite.holdings()),
            ("Positions", lambda: self.kite.positions()),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                print(f"✅ {test_name}: OK")
            except Exception as e:
                print(f"❌ {test_name}: {str(e)[:50]}...")
                return False
        
        print("🎉 All API tests passed!")
        return True

def main():
    """Main function demonstrating token management"""
    print("🔑 KITE TOKEN MANAGER")
    print("=" * 30)
    
    # Initialize token manager
    manager = KiteTokenManager(API_KEY)
    
    # Get API secret (you can also store this securely)
    print("📝 You need your API Secret for authentication")
    print("Find it in your Kite Developer Console: https://developers.kite.trade/")
    api_secret = input("🔒 Enter API Secret (or press Enter to use .env value / skip if saved session): ").strip() or API_SECRET_DEFAULT
    
    # Ensure we're authenticated
    if manager.ensure_authenticated(api_secret):
        print("\n" + "="*50)
        print("🎉 AUTHENTICATION SUCCESSFUL!")
        
        # Show session status
        status = manager.get_session_status()
        print(f"👤 User ID: {status['user_id']}")
        print(f"🔐 Token Valid: {status['token_valid']}")
        if status['token_expiry']:
            expiry = datetime.fromisoformat(status['token_expiry'])
            print(f"⏰ Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Test API calls
        manager.test_api_calls()
        
        print("\n💡 IMPORTANT NOTES:")
        print("- Your access token is saved and will be reused")
        print("- Token expires daily around 3:30 PM IST")
        print("- Run this script daily to refresh your token")
        print("- Request tokens are single-use only")
        
    else:
        print("❌ Authentication failed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"\n💥 Error: {e}")
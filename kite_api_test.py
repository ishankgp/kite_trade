#!/usr/bin/env python3
"""
Kite Connect API Test & Utility Script
=====================================

Combined quick validation and full authentication / endpoint testing tool for
Zerodha Kite Connect. Replaces the former separate quick_kite_test script.

Features:
* Quick checks: API key format, KiteConnect init, login URL generation, redirect URL reachability
* Full auth: Guides through manual request_token exchange to get access token
* Endpoint tests: profile, margins, holdings, positions, orders, instruments, quote
* Interactive shell: ad‑hoc queries after authentication

Usage Examples:
    Quick validation only:
        python3 kite_api_test.py --quick

    Full authentication flow (then run endpoint tests):
        python3 kite_api_test.py

    Full auth + skip endpoint tests and jump straight to interactive shell:
        python3 kite_api_test.py --interactive

    Run quick validation first, then (if all pass) proceed to full flow:
        python3 kite_api_test.py --quick --full

Arguments:
    --quick        Run only the quick pre-auth validations and exit (unless --full also given)
    --full         Force full flow even if --quick is supplied
    --interactive  After successful auth, drop into interactive shell automatically

Documentation: https://kite.trade/docs/connect/v3/
"""

import os
import sys
import time
import argparse
import requests
from kiteconnect import KiteConnect
from env_loader import get_kite_config

# Load credentials from environment
_cfg = get_kite_config()
API_KEY = _cfg['api_key']
REDIRECT_URL = _cfg['redirect_url']

# Initialize Kite Connect
kite = KiteConnect(api_key=API_KEY)


# ---------------------- Quick Validation Functions ---------------------- #
def quick_test_api_key_format():
    print("🔍 Testing API Key Format...")
    if len(API_KEY) not in (16, 32):
        print(f"❌ API Key length incorrect. Expected 16 or 32 chars, got {len(API_KEY)}")
        return False
    if not API_KEY.isalnum():
        print("❌ API Key contains invalid characters. Should be alphanumeric only.")
        return False
    print("✅ API Key format looks valid")
    return True

def quick_test_kite_init():
    print("\n🔧 Testing KiteConnect Initialization...")
    try:
        _ = KiteConnect(api_key=API_KEY)
        print("✅ KiteConnect initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize KiteConnect: {e}")
        return False

def quick_test_login_url():
    print("\n🔗 Testing Login URL Generation...")
    try:
        url = kite.login_url()
        print(f"✅ Login URL generated: {url[:60]}...")
        if "kite.zerodha.com" in url and API_KEY in url:
            print("✅ Login URL contains correct components")
            return True
        print("⚠️  Login URL missing expected components")
        return False
    except Exception as e:
        print(f"❌ Failed to generate login URL: {e}")
        return False

def quick_test_redirect_reachability():
    print("\n🌐 Testing Redirect URL Accessibility...")
    print(f"Testing: {REDIRECT_URL}")
    try:
        resp = requests.get(REDIRECT_URL, timeout=10)
        if resp.status_code == 200:
            print("✅ Redirect URL is accessible (HTTP 200)")
            return True
        print(f"⚠️  Redirect URL returned status {resp.status_code}")
        return False
    except requests.exceptions.Timeout:
        print("❌ Redirect URL timeout - may not be accessible")
        return False
    except Exception as e:
        print(f"❌ Failed to access redirect URL: {e}")
        return False

def run_quick_suite():
    print("🚀 KITE API QUICK VALIDATION")
    print("=" * 40)
    print(f"API Key: {API_KEY}")
    print(f"Redirect URL: {REDIRECT_URL}")
    print()
    results = [
        ("API Key Format", quick_test_api_key_format()),
        ("KiteConnect Init", quick_test_kite_init()),
        ("Login URL Generation", quick_test_login_url()),
        ("Redirect URL Access", quick_test_redirect_reachability()),
    ]
    print("\n📊 VALIDATION SUMMARY")
    print("=" * 25)
    all_passed = True
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{name:20} : {status}")
        if not ok:
            all_passed = False
    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 ALL QUICK TESTS PASSED!")
    else:
        print("⚠️  SOME QUICK TESTS FAILED. Review above before proceeding.")
    return all_passed

class KiteAPITester:
    def __init__(self):
        self.access_token = None
        self.user_id = None
        
    def step1_generate_login_url(self):
        """Step 1: Generate login URL and open in browser"""
        print("🚀 KITE API AUTHENTICATION TEST")
        print("=" * 50)
        print(f"📊 API Key: {API_KEY}")
        print(f"🔗 Redirect URL: {REDIRECT_URL}")
        print()
        
        # Generate login URL
        login_url = kite.login_url()
        print("🔑 Step 1: Authentication")
        print(f"Login URL: {login_url}")
        print()
        print("👆 Click the URL above or copy-paste it in your browser")
        print("🔐 Login with your Zerodha credentials")
        print("📋 After login, you'll be redirected to your callback URL")
        print("🎯 Copy the 'request_token' from the URL and paste it below")
        print()
        
        return login_url
    
    def step2_get_access_token(self, request_token, api_secret):
        """Step 2: Exchange request token for access token"""
        try:
            print(f"🔄 Step 2: Exchanging request_token for access_token...")
            
            # Generate access token
            data = kite.generate_session(request_token, api_secret)
            
            self.access_token = data["access_token"]
            self.user_id = data["user_id"]
            
            print("✅ Authentication Successful!")
            print(f"🆔 User ID: {self.user_id}")
            print(f"🔐 Access Token: {self.access_token[:20]}...")
            print()
            
            # Set access token for subsequent API calls
            kite.set_access_token(self.access_token)
            
            return True
            
        except Exception as e:
            print(f"❌ Authentication Failed: {e}")
            return False
    
    def step3_test_api_endpoints(self):
        """Step 3: Test various API endpoints"""
        if not self.access_token:
            print("❌ No access token available. Complete authentication first.")
            return
        
        print("🧪 Step 3: Testing API Endpoints")
        print("-" * 30)
        
        test_functions = [
            ("User Profile", self.test_profile),
            ("Account Margins", self.test_margins), 
            ("Holdings", self.test_holdings),
            ("Positions", self.test_positions),
            ("Orders", self.test_orders),
            ("Instruments", self.test_instruments),
            ("Quote", self.test_quote),
        ]
        
        results = {}
        for test_name, test_func in test_functions:
            try:
                print(f"🔍 Testing {test_name}...")
                result = test_func()
                results[test_name] = "✅ PASS" if result else "❌ FAIL"
                time.sleep(1)  # Rate limiting
            except Exception as e:
                results[test_name] = f"❌ ERROR: {str(e)[:50]}..."
                print(f"   Error: {e}")
        
        # Print summary
        print("\n📊 TEST RESULTS SUMMARY")
        print("=" * 30)
        for test_name, result in results.items():
            print(f"{test_name:15} : {result}")
    
    def test_profile(self):
        """Test user profile endpoint"""
        profile = kite.profile()
        print(f"   👤 User: {profile.get('user_name', 'N/A')}")
        print(f"   📧 Email: {profile.get('email', 'N/A')}")
        print(f"   📱 Broker: {profile.get('broker', 'N/A')}")
        return bool(profile.get('user_id'))
    
    def test_margins(self):
        """Test margins endpoint"""
        margins = kite.margins()
        equity_available = margins.get('equity', {}).get('available', {}).get('cash', 0)
        print(f"   💰 Available Cash: ₹{equity_available:,.2f}")
        return 'equity' in margins
    
    def test_holdings(self):
        """Test holdings endpoint"""
        holdings = kite.holdings()
        print(f"   📈 Holdings Count: {len(holdings)}")
        if holdings:
            for holding in holdings[:3]:  # Show first 3
                print(f"   📊 {holding.get('tradingsymbol', 'N/A')}: {holding.get('quantity', 0)} shares")
        return isinstance(holdings, list)
    
    def test_positions(self):
        """Test positions endpoint"""
        positions = kite.positions()
        net_positions = positions.get('net', [])
        day_positions = positions.get('day', [])
        print(f"   📍 Net Positions: {len(net_positions)}")
        print(f"   📍 Day Positions: {len(day_positions)}")
        return 'net' in positions and 'day' in positions
    
    def test_orders(self):
        """Test orders endpoint"""
        orders = kite.orders()
        print(f"   📋 Orders Count: {len(orders)}")
        if orders:
            recent_orders = [o for o in orders if o.get('status') in ['COMPLETE', 'OPEN']]
            print(f"   📋 Recent Orders: {len(recent_orders)}")
        return isinstance(orders, list)
    
    def test_instruments(self):
        """Test instruments endpoint"""
        # Get NSE instruments (limited for testing)
        instruments = kite.instruments("NSE")
        print(f"   🏛️ NSE Instruments: {len(instruments)}")
        return len(instruments) > 0
    
    def test_quote(self):
        """Test quote endpoint with a popular stock"""
        try:
            # Test with Reliance (a popular stock)
            quote = kite.quote(["NSE:RELIANCE"])
            if "NSE:RELIANCE" in quote:
                price = quote["NSE:RELIANCE"]["last_price"]
                print(f"   📈 RELIANCE Price: ₹{price}")
                return True
            return False
        except:
            # Fallback: just test if the endpoint responds
            try:
                quote = kite.quote(["NSE:SBIN"])  # State Bank
                return bool(quote)
            except:
                return False
    
    def interactive_mode(self):
        """Interactive mode for manual testing"""
        print("\n🎮 INTERACTIVE MODE")
        print("Enter 'help' for available commands, 'quit' to exit")
        
        while True:
            try:
                cmd = input("\nkite> ").strip().lower()
                
                if cmd == 'quit' or cmd == 'exit':
                    break
                elif cmd == 'help':
                    self.show_help()
                elif cmd == 'profile':
                    print(kite.profile())
                elif cmd == 'margins':
                    print(kite.margins())
                elif cmd == 'holdings':
                    print(kite.holdings())
                elif cmd == 'positions':
                    print(kite.positions())
                elif cmd == 'orders':
                    print(kite.orders())
                elif cmd.startswith('quote '):
                    symbol = cmd.split(' ', 1)[1].upper()
                    if ':' not in symbol:
                        symbol = f"NSE:{symbol}"
                    print(kite.quote([symbol]))
                elif cmd == 'instruments':
                    instruments = kite.instruments("NSE")
                    print(f"Found {len(instruments)} NSE instruments")
                    print("First 5:", [i['tradingsymbol'] for i in instruments[:5]])
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def show_help(self):
        """Show available commands"""
        commands = [
            "profile     - Show user profile",
            "margins     - Show account margins", 
            "holdings    - Show current holdings",
            "positions   - Show current positions",
            "orders      - Show order history",
            "instruments - List available instruments",
            "quote SYMBOL - Get quote for symbol (e.g., 'quote RELIANCE')",
            "help        - Show this help",
            "quit        - Exit interactive mode"
        ]
        
        print("\nAvailable commands:")
        for cmd in commands:
            print(f"  {cmd}")

def main(argv=None):
    parser = argparse.ArgumentParser(description="Kite Connect quick + full test utility")
    parser.add_argument("--quick", action="store_true", help="Run quick validation tests and exit (unless --full specified)")
    parser.add_argument("--full", action="store_true", help="Run full auth flow (use with --quick to chain)")
    parser.add_argument("--interactive", action="store_true", help="Enter interactive shell after full auth")
    args = parser.parse_args(argv)

    performed_full = False

    if args.quick:
        all_ok = run_quick_suite()
        if not all_ok and not args.full:
            print("\n❌ Aborting before full flow due to failed quick tests (use --full to force).")
            return
        if not args.full:
            return  # only quick requested

    # Full flow requested explicitly OR implicit when neither quick nor full flags given
    if args.full or (not args.quick and not args.full):
        tester = KiteAPITester()
        tester.step1_generate_login_url()
        print("📋 MANUAL INPUT REQUIRED:")
        print("1. Open the login URL above in your browser")
        print("2. Login with your Zerodha credentials")
        print("3. Copy the 'request_token' from the redirected URL")
        print("4. Paste it below:")
        print()
        request_token = input("🔑 Enter request_token: ").strip()
        if not request_token:
            print("❌ No request_token provided. Exiting.")
            return
        print("\n🔐 SECURITY NOTE:")
        print("You need your API SECRET to complete authentication.")
        print("Find it in your Kite Developer Console.")
        print()
        api_secret = os.getenv("KITE_API_SECRET") or input("🔒 Enter API Secret: ").strip()
        if not api_secret:
            print("❌ No API secret provided. Exiting.")
            return
        if tester.step2_get_access_token(request_token, api_secret):
            tester.step3_test_api_endpoints()
            performed_full = True
            if args.interactive:
                tester.interactive_mode()
            else:
                choice = input("\n🎮 Enter interactive mode? (y/n): ").strip().lower()
                if choice == 'y':
                    tester.interactive_mode()
        print("\n🎉 Kite API Test Complete!")

    if not performed_full and not args.quick:
        print("Nothing executed. Use --quick and/or --full. See --help.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("Check your API credentials and try again.")
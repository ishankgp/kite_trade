#!/usr/bin/env python3
"""
Quick Kite API Health Check
===========================

Runs pre-auth quick checks and, if requested, performs a minimal authenticated
endpoint check suite to verify the Kite APIs are working.

Usage:
  python3 quick_kite_test.py            # quick checks only
  python3 quick_kite_test.py --full     # quick + minimal authenticated tests
"""

import os
import argparse
import requests
from kiteconnect import KiteConnect
from env_loader import get_kite_config

_cfg = get_kite_config()
API_KEY = _cfg['api_key']
REDIRECT_URL = _cfg['redirect_url']


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


def quick_test_login_url(kite: KiteConnect):
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
    kite = KiteConnect(api_key=API_KEY)
    print("🚀 KITE API QUICK VALIDATION")
    print("=" * 40)
    print(f"API Key: {API_KEY}")
    print(f"Redirect URL: {REDIRECT_URL}")
    print()

    results = [
        ("API Key Format", quick_test_api_key_format()),
        ("KiteConnect Init", quick_test_kite_init()),
        ("Login URL Generation", quick_test_login_url(kite)),
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


def run_minimal_authenticated_tests():
    print("\n🔐 Minimal Authenticated Tests")
    print("-" * 30)
    kite = KiteConnect(api_key=API_KEY)
    login_url = kite.login_url()
    print(f"Login URL: {login_url}")
    print("Follow the URL, login, then paste the request_token below.")
    request_token = input("🔑 Enter request_token: ").strip()
    if not request_token:
        print("❌ No request_token provided.")
        return False
    api_secret = os.getenv("KITE_API_SECRET") or input("🔒 Enter API Secret: ").strip()
    if not api_secret:
        print("❌ No API secret provided.")
        return False
    try:
        data = kite.generate_session(request_token, api_secret)
        kite.set_access_token(data["access_token"])
    except Exception as e:
        print(f"❌ Authentication Failed: {e}")
        return False

    try:
        print("🔍 profile...")
        _ = kite.profile()
        print("✅ profile OK")
        print("🔍 margins...")
        _ = kite.margins()
        print("✅ margins OK")
        print("🔍 quote RELIANCE...")
        q = kite.quote(["NSE:RELIANCE"])
        ok = "NSE:RELIANCE" in q
        print("✅ quote OK" if ok else "⚠️ quote returned no RELIANCE data")
        return ok or True
    except Exception as e:
        print(f"❌ Endpoint test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Quick Kite API health check")
    parser.add_argument("--full", action="store_true", help="Run minimal authenticated endpoint tests after quick checks")
    args = parser.parse_args()

    ok = run_quick_suite()
    if not args.full:
        return
    if not ok:
        print("\n⚠️  Proceeding to authenticated tests despite quick failures.")
    run_minimal_authenticated_tests()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"\n💥 Error: {e}")
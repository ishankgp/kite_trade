#!/usr/bin/env python3
"""
Daily Kite Token Renewal Script
==============================

This script should be run daily (preferably in the morning before market opens)
to ensure you have a valid access token for trading.

Schedule this script to run automatically:
- As a cron job
- In your trading bot startup routine
- Manually each trading day
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta
from kite_token_manager import KiteTokenManager
from env_loader import get_kite_config

# Configuration (loaded from .env)
_cfg = get_kite_config()
API_KEY = _cfg['api_key']
TOKEN_FILE = "/workspaces/kite_trade/access_token.json"

# Legacy config removal note: kite_config.ini support removed after consolidation.

def is_trading_day():
    """Check if today is a trading day (Monday-Friday, excluding holidays)"""
    today = datetime.now()
    
    # Check if it's a weekend
    if today.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    
    # TODO: Add holiday calendar check
    # For now, assume all weekdays are trading days
    return True

def check_token_status():
    """Check current token status"""
    if not os.path.exists(TOKEN_FILE):
        return False, "No saved token found"
    
    try:
        with open(TOKEN_FILE, 'r') as f:
            data = json.load(f)
        
        expiry_time = datetime.fromisoformat(data.get('expiry', ''))
        current_time = datetime.now(timezone.utc)
        
        if current_time < expiry_time:
            hours_left = (expiry_time - current_time).total_seconds() / 3600
            return True, f"Token valid for {hours_left:.1f} more hours"
        else:
            return False, "Token has expired"
            
    except Exception as e:
        return False, f"Error reading token: {e}"

def main():
    """Main renewal process"""
    print("🔄 DAILY KITE TOKEN RENEWAL")
    print("=" * 35)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if it's a trading day
    if not is_trading_day():
        print("📴 Today is not a trading day (weekend)")
        print("💤 Skipping token renewal")
        return
    
    print("📈 Trading day detected")
    
    # Check current token status
    is_valid, status_msg = check_token_status()
    print(f"🔍 Current token status: {status_msg}")
    
    if is_valid:
        print("✅ Token is still valid, no renewal needed")
        
        # Test if token actually works
        manager = KiteTokenManager(API_KEY)
        manager.load_saved_session()
        
        if manager.is_token_valid():
            print("✅ Token validation test passed")
            return
        else:
            print("⚠️  Token validation failed, forcing renewal")
    
    # Need to renew token
    print("🔄 Token renewal required")
    
    # Use secret from environment
    api_secret = _cfg['api_secret']
    if not api_secret:
        print("❌ API secret missing in environment (.env)")
        return
    
    # Perform renewal
    manager = KiteTokenManager(API_KEY)
    
    print("\n🔐 Starting authentication process...")
    if manager.ensure_authenticated(api_secret):
        print("🎉 Token renewal successful!")
        
        # Test the new token
        if manager.test_api_calls():
            print("✅ New token is working correctly")
        else:
            print("⚠️  New token test failed")
    else:
        print("❌ Token renewal failed")

def schedule_info():
    """Show information about scheduling this script"""
    print("\n📅 SCHEDULING INFORMATION")
    print("=" * 30)
    print("This script should run daily before market hours.")
    print("\n🕐 Recommended schedule:")
    print("- 8:00 AM IST (before market opens at 9:15 AM)")
    print("- Monday to Friday only")
    print("\n⚙️  To schedule with cron:")
    print("# Add this line to your crontab (crontab -e)")
    print("0 8 * * 1-5 /usr/bin/python3 /workspaces/kite_trade/daily_token_renewal.py")
    print("\n🤖 In your trading bot:")
    print("Run this script in your bot's startup routine")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "schedule-info":
        schedule_info()
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\n👋 Renewal interrupted")
        except Exception as e:
            print(f"\n💥 Error: {e}")
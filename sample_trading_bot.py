#!/usr/bin/env python3
"""
Sample Trading Bot with Automatic Token Management
=================================================

This demonstrates how to build a trading bot that automatically handles
Kite token renewal and authentication.

Features:
- Automatic token loading/renewal
- Error handling for expired tokens
- Clean session management
- Ready for live trading integration
"""

import time
import sys
from datetime import datetime
from kite_token_manager import KiteTokenManager
from env_loader import get_kite_config

class TradingBot:
    def __init__(self, api_key, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_manager = KiteTokenManager(api_key, api_secret)
        self.is_authenticated = False
        
    def start(self):
        """Start the trading bot"""
        print("🤖 TRADING BOT STARTING")
        print("=" * 25)
        
        # Step 1: Ensure authentication
        if not self.authenticate():
            print("❌ Failed to authenticate. Bot cannot start.")
            return False
        
        # Step 2: Initialize trading systems
        if not self.initialize():
            print("❌ Failed to initialize. Bot cannot start.")
            return False
        
        # Step 3: Start main trading loop
        print("🚀 Bot is now running...")
        self.run_trading_loop()
        
        return True
    
    def authenticate(self):
        """Handle authentication with automatic token management"""
        print("🔐 Authenticating with Kite...")
        
        try:
            # Try to use saved session first
            if self.token_manager.load_saved_session():
                if self.token_manager.is_token_valid():
                    print("✅ Using valid saved session")
                    self.is_authenticated = True
                    return True
            
            # Need fresh authentication
            print("🔄 Fresh authentication required")
            
            if not self.api_secret:
                print("📝 API Secret required for authentication")
                self.api_secret = input("🔒 Enter API Secret: ").strip()
            
            if self.token_manager.ensure_authenticated(self.api_secret):
                self.is_authenticated = True
                print("✅ Authentication successful")
                return True
            else:
                print("❌ Authentication failed")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def initialize(self):
        """Initialize trading systems"""
        print("⚙️  Initializing trading systems...")
        
        try:
            # Get user profile
            profile = self.token_manager.kite.profile()
            print(f"👤 Logged in as: {profile.get('user_name', 'Unknown')}")
            
            # Check account status
            margins = self.token_manager.kite.margins()
            available_cash = margins.get('equity', {}).get('available', {}).get('cash', 0)
            print(f"💰 Available cash: ₹{available_cash:,.2f}")
            
            # Get current positions
            positions = self.token_manager.kite.positions()
            net_positions = positions.get('net', [])
            print(f"📍 Current positions: {len(net_positions)}")
            
            # Initialize your trading strategy here
            self.initialize_strategy()
            
            return True
            
        except Exception as e:
            print(f"❌ Initialization error: {e}")
            return False
    
    def initialize_strategy(self):
        """Initialize your trading strategy"""
        print("📊 Initializing trading strategy...")
        
        # Example: Set up instruments to monitor
        self.watchlist = [
            "NSE:RELIANCE",
            "NSE:TCS", 
            "NSE:INFY",
            "NSE:HDFCBANK",
            "NSE:ICICIBANK"
        ]
        
        print(f"👀 Watchlist: {len(self.watchlist)} instruments")
        
        # Example: Load any saved strategy state
        # self.load_strategy_state()
        
        print("✅ Strategy initialized")
    
    def run_trading_loop(self):
        """Main trading loop"""
        print("🔄 Starting trading loop...")
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                current_time = datetime.now()
                
                print(f"\n🔄 Loop {loop_count} - {current_time.strftime('%H:%M:%S')}")
                
                # Check if token is still valid
                if not self.check_token_validity():
                    print("🔄 Re-authenticating...")
                    if not self.authenticate():
                        print("❌ Re-authentication failed. Stopping bot.")
                        break
                
                # Run your trading logic
                self.execute_trading_logic()
                
                # Sleep before next iteration
                print("😴 Sleeping for 60 seconds...")
                time.sleep(60)  # Run every minute
                
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
        except Exception as e:
            print(f"\n💥 Unexpected error: {e}")
        finally:
            self.cleanup()
    
    def check_token_validity(self):
        """Check if current token is still valid"""
        try:
            return self.token_manager.is_token_valid()
        except:
            return False
    
    def execute_trading_logic(self):
        """Your trading logic goes here"""
        try:
            # Example: Get quotes for watchlist
            quotes = self.token_manager.kite.quote(self.watchlist)
            
            print(f"📈 Market data received for {len(quotes)} instruments")
            
            # Example: Simple price monitoring
            for symbol in self.watchlist[:2]:  # Just show first 2
                if symbol in quotes:
                    price = quotes[symbol]['last_price']
                    change = quotes[symbol]['net_change']
                    print(f"   {symbol}: ₹{price} ({change:+.2f})")
            
            # YOUR TRADING STRATEGY HERE
            # Example decisions:
            # - Check technical indicators
            # - Evaluate market conditions  
            # - Place buy/sell orders
            # - Manage existing positions
            # - Risk management
            
            self.check_positions()
            
        except Exception as e:
            print(f"⚠️  Trading logic error: {e}")
    
    def check_positions(self):
        """Check and manage current positions"""
        try:
            positions = self.token_manager.kite.positions()
            net_positions = positions.get('net', [])
            
            active_positions = [p for p in net_positions if p['quantity'] != 0]
            
            if active_positions:
                print(f"📍 Active positions: {len(active_positions)}")
                for pos in active_positions:
                    symbol = pos['tradingsymbol']
                    qty = pos['quantity']
                    pnl = pos['pnl']
                    print(f"   {symbol}: {qty} shares, P&L: ₹{pnl:,.2f}")
            
        except Exception as e:
            print(f"⚠️  Position check error: {e}")
    
    def cleanup(self):
        """Cleanup when bot stops"""
        print("🧹 Cleaning up...")
        
        # Save any important state
        # Close open orders if needed
        # Log final status
        
        print("✅ Cleanup complete")

def main():
    """Main function"""
    cfg = get_kite_config()
    API_KEY = cfg['api_key']
    
    print("🤖 SAMPLE TRADING BOT")
    print("=" * 20)
    print("This is a demo bot showing proper token management")
    print("Modify the trading logic for your strategy")
    print()
    
    # Create and start bot
    bot = TradingBot(API_KEY)
    
    if bot.start():
        print("🎉 Bot completed successfully")
    else:
        print("❌ Bot failed to start")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Error: {e}")
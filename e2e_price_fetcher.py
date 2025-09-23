#!/usr/bin/env python3
"""
E2E Networks Price Data Fetcher
==============================

This script demonstrates fetching E2E Networks (NSE:E2E) price data
using the Kite Connect API with various methods:

1. Real-time quotes
2. Historical data
3. Market depth
4. OHLC data
5. Instrument details
"""

import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from kite_token_manager import KiteTokenManager
from env_loader import get_kite_config

# Load credentials from environment
_cfg = get_kite_config()
API_KEY = _cfg['api_key']
API_SECRET = _cfg['api_secret']

# E2E Networks instrument
E2E_SYMBOL = "NSE:E2E"

class E2EPriceAnalyzer:
    def __init__(self):
        self.token_manager = KiteTokenManager(API_KEY)
        self.kite = None
        self.instrument_token = None
        
    def initialize(self):
        """Initialize and authenticate"""
        print("🔐 Initializing E2E Price Analyzer...")
        
        # Load saved session or authenticate
        if self.token_manager.load_saved_session():
            if self.token_manager.is_token_valid():
                print("✅ Using saved authentication session")
                self.kite = self.token_manager.kite
                return True
        
        print("❌ No valid session found. Please run kite_token_manager.py first")
        return False
    
    def get_instrument_details(self):
        """Get E2E instrument details"""
        print(f"\n📊 Getting instrument details for {E2E_SYMBOL}...")
        
        try:
            # Get all NSE instruments
            instruments = self.kite.instruments("NSE")
            
            # Find E2E instrument
            e2e_instrument = None
            for instrument in instruments:
                if instrument['tradingsymbol'] == 'E2E':
                    e2e_instrument = instrument
                    break
            
            if e2e_instrument:
                self.instrument_token = e2e_instrument['instrument_token']
                print("✅ E2E Networks Instrument Found:")
                print(f"   📈 Symbol: {e2e_instrument['tradingsymbol']}")
                print(f"   🏢 Company: {e2e_instrument['name']}")
                print(f"   🔢 Token: {e2e_instrument['instrument_token']}")
                print(f"   💰 Lot Size: {e2e_instrument['lot_size']}")
                print(f"   📊 Segment: {e2e_instrument['segment']}")
                print(f"   💱 Exchange: {e2e_instrument['exchange']}")
                return e2e_instrument
            else:
                print("❌ E2E instrument not found")
                return None
                
        except Exception as e:
            print(f"❌ Error getting instrument details: {e}")
            return None
    
    def get_realtime_quote(self):
        """Get real-time quote for E2E"""
        print(f"\n📈 Getting real-time quote for {E2E_SYMBOL}...")
        
        try:
            quote = self.kite.quote([E2E_SYMBOL])
            
            if E2E_SYMBOL in quote:
                e2e_quote = quote[E2E_SYMBOL]
                
                print("✅ Real-time Quote Data:")
                print(f"   💰 Last Price: ₹{e2e_quote['last_price']}")
                print(f"   📊 Open: ₹{e2e_quote['ohlc']['open']}")
                print(f"   📈 High: ₹{e2e_quote['ohlc']['high']}")
                print(f"   📉 Low: ₹{e2e_quote['ohlc']['low']}")
                print(f"   🔒 Close: ₹{e2e_quote['ohlc']['close']}")
                print(f"   📊 Volume: {e2e_quote['volume']:,}")
                print(f"   🔄 Change: ₹{e2e_quote['net_change']} ({e2e_quote['net_change']/e2e_quote['last_price']*100:.2f}%)")
                print(f"   🕐 Last Trade Time: {e2e_quote['last_trade_time']}")
                
                # Market depth
                if 'depth' in e2e_quote:
                    print("\n📋 Market Depth:")
                    depth = e2e_quote['depth']
                    
                    print("   🟢 Buy Orders:")
                    for i, buy in enumerate(depth['buy'][:3], 1):
                        print(f"      {i}. ₹{buy['price']} x {buy['quantity']}")
                    
                    print("   🔴 Sell Orders:")
                    for i, sell in enumerate(depth['sell'][:3], 1):
                        print(f"      {i}. ₹{sell['price']} x {sell['quantity']}")
                
                return e2e_quote
            else:
                print("❌ Quote data not available")
                return None
                
        except Exception as e:
            print(f"❌ Error getting quote: {e}")
            return None
    
    def get_ohlc_data(self):
        """Get OHLC data for E2E"""
        print(f"\n📊 Getting OHLC data for {E2E_SYMBOL}...")
        
        try:
            ohlc = self.kite.ohlc([E2E_SYMBOL])
            
            if E2E_SYMBOL in ohlc:
                e2e_ohlc = ohlc[E2E_SYMBOL]
                
                print("✅ OHLC Data:")
                print(f"   📊 Open: ₹{e2e_ohlc['ohlc']['open']}")
                print(f"   📈 High: ₹{e2e_ohlc['ohlc']['high']}")
                print(f"   📉 Low: ₹{e2e_ohlc['ohlc']['low']}")
                print(f"   🔒 Close: ₹{e2e_ohlc['ohlc']['close']}")
                print(f"   💰 Last Price: ₹{e2e_ohlc['last_price']}")
                print(f"   📊 Volume: {e2e_ohlc['volume']:,}")
                
                return e2e_ohlc
            else:
                print("❌ OHLC data not available")
                return None
                
        except Exception as e:
            print(f"❌ Error getting OHLC: {e}")
            return None
    
    def get_historical_data(self, days=30):
        """Get historical data for E2E"""
        print(f"\n📈 Getting {days} days historical data for {E2E_SYMBOL}...")
        
        if not self.instrument_token:
            print("❌ Instrument token not available. Get instrument details first.")
            return None
        
        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            # Get historical data
            historical_data = self.kite.historical_data(
                instrument_token=self.instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            if historical_data:
                print(f"✅ Retrieved {len(historical_data)} days of historical data")
                
                # Convert to DataFrame for analysis
                df = pd.DataFrame(historical_data)
                
                # Show latest 5 days
                print("\n📅 Latest 5 Days:")
                print("   Date       | Open    | High    | Low     | Close   | Volume")
                print("   " + "-" * 65)
                
                for _, row in df.tail(5).iterrows():
                    date_str = row['date'].strftime('%Y-%m-%d')
                    print(f"   {date_str} | ₹{row['open']:6.2f} | ₹{row['high']:6.2f} | ₹{row['low']:6.2f} | ₹{row['close']:6.2f} | {row['volume']:,}")
                
                # Basic statistics
                print(f"\n📊 {days}-Day Statistics:")
                print(f"   📈 Highest: ₹{df['high'].max():.2f}")
                print(f"   📉 Lowest: ₹{df['low'].min():.2f}")
                print(f"   📊 Average Close: ₹{df['close'].mean():.2f}")
                print(f"   📊 Average Volume: {df['volume'].mean():,.0f}")
                
                # Recent performance
                if len(df) >= 2:
                    latest_close = df.iloc[-1]['close']
                    previous_close = df.iloc[-2]['close']
                    change = latest_close - previous_close
                    change_pct = (change / previous_close) * 100
                    print(f"   🔄 Latest Change: ₹{change:.2f} ({change_pct:+.2f}%)")
                
                return df
            else:
                print("❌ No historical data available")
                return None
                
        except Exception as e:
            print(f"❌ Error getting historical data: {e}")
            return None
    
    def save_data_to_csv(self, df, filename="e2e_historical_data.csv"):
        """Save historical data to CSV"""
        if df is not None:
            try:
                filepath = f"/workspaces/kite_trade/{filename}"
                df.to_csv(filepath, index=False)
                print(f"💾 Historical data saved to: {filepath}")
                return filepath
            except Exception as e:
                print(f"❌ Error saving data: {e}")
                return None
        return None
    
    def get_ltp(self):
        """Get Last Traded Price quickly"""
        print(f"\n⚡ Getting LTP for {E2E_SYMBOL}...")
        
        try:
            ltp = self.kite.ltp([E2E_SYMBOL])
            
            if E2E_SYMBOL in ltp:
                price = ltp[E2E_SYMBOL]['last_price']
                print(f"✅ E2E Networks LTP: ₹{price}")
                return price
            else:
                print("❌ LTP not available")
                return None
                
        except Exception as e:
            print(f"❌ Error getting LTP: {e}")
            return None
    
    def comprehensive_analysis(self):
        """Run comprehensive analysis of E2E Networks"""
        print("🚀 E2E NETWORKS COMPREHENSIVE ANALYSIS")
        print("=" * 50)
        
        # Step 1: Get instrument details
        instrument = self.get_instrument_details()
        if not instrument:
            return False
        
        # Step 2: Get real-time quote
        quote = self.get_realtime_quote()
        
        # Step 3: Get OHLC data
        ohlc = self.get_ohlc_data()
        
        # Step 4: Get historical data
        historical_df = self.get_historical_data(30)
        
        # Step 5: Save data
        if historical_df is not None:
            self.save_data_to_csv(historical_df)
        
        # Step 6: Quick LTP check
        self.get_ltp()
        
        print("\n🎉 Analysis Complete!")
        print("📊 All E2E Networks data has been retrieved successfully")
        
        return True

def main():
    """Main function"""
    print("📈 E2E NETWORKS PRICE DATA FETCHER")
    print("=" * 40)
    
    analyzer = E2EPriceAnalyzer()
    
    # Initialize
    if not analyzer.initialize():
        print("❌ Failed to initialize. Please authenticate first.")
        print("💡 Run: python3 kite_token_manager.py")
        return
    
    # Run comprehensive analysis
    analyzer.comprehensive_analysis()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Analysis interrupted")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
#!/usr/bin/env python3
"""
E2E Networks Price Visualization
==============================

Simple script to visualize E2E price trends using the downloaded data.
"""

import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def create_price_chart():
    """Create a simple price chart for E2E Networks"""
    try:
        # Read the CSV data
        df = pd.read_csv('/workspaces/kite_trade/e2e_historical_data.csv')
        df['date'] = pd.to_datetime(df['date'])
        
        print("📊 E2E NETWORKS PRICE VISUALIZATION")
        print("=" * 40)
        print(f"📅 Data Period: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
        print(f"📈 Data Points: {len(df)} days")
        
        # Create the plot
        plt.figure(figsize=(12, 8))
        
        # Plot candlestick-style chart
        plt.subplot(2, 1, 1)
        plt.plot(df['date'], df['close'], 'b-', linewidth=2, label='Close Price')
        plt.plot(df['date'], df['high'], 'g--', alpha=0.7, label='Daily High')
        plt.plot(df['date'], df['low'], 'r--', alpha=0.7, label='Daily Low')
        plt.fill_between(df['date'], df['low'], df['high'], alpha=0.2, color='gray')
        
        plt.title('E2E Networks (NSE:E2E) - Price Movement', fontsize=16, fontweight='bold')
        plt.ylabel('Price (₹)', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Plot volume
        plt.subplot(2, 1, 2)
        plt.bar(df['date'], df['volume'], alpha=0.7, color='orange')
        plt.title('Trading Volume', fontsize=14)
        plt.ylabel('Volume (Shares)', fontsize=12)
        plt.xlabel('Date', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Save the chart
        chart_file = '/workspaces/kite_trade/e2e_price_chart.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        print(f"📊 Chart saved: {chart_file}")
        
        # Show key statistics
        print(f"\n💹 KEY STATISTICS:")
        print(f"   Current Price: ₹{df['close'].iloc[-1]:,.2f}")
        print(f"   30-Day High: ₹{df['high'].max():,.2f}")
        print(f"   30-Day Low: ₹{df['low'].min():,.2f}")
        print(f"   Average Volume: {df['volume'].mean():,.0f}")
        
        # Calculate returns
        if len(df) > 1:
            total_return = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
            print(f"   30-Day Return: {total_return:+.2f}%")
        
        return True
        
    except FileNotFoundError:
        print("❌ CSV file not found. Run e2e_price_fetcher.py first.")
        return False
    except Exception as e:
        print(f"❌ Error creating chart: {e}")
        return False

def analyze_recent_performance():
    """Analyze recent performance"""
    try:
        df = pd.read_csv('/workspaces/kite_trade/e2e_historical_data.csv')
        df['date'] = pd.to_datetime(df['date'])
        
        print(f"\n📈 RECENT PERFORMANCE ANALYSIS")
        print("=" * 35)
        
        # Last 5 days analysis
        recent = df.tail(5)
        print("📅 Last 5 Trading Days:")
        
        for _, row in recent.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d (%a)')
            daily_change = row['close'] - row['open']
            daily_change_pct = (daily_change / row['open']) * 100
            
            change_icon = "📈" if daily_change > 0 else "📉" if daily_change < 0 else "➡️"
            
            print(f"   {change_icon} {date_str}")
            print(f"      Open: ₹{row['open']:,.2f} → Close: ₹{row['close']:,.2f}")
            print(f"      Change: ₹{daily_change:+,.2f} ({daily_change_pct:+.2f}%)")
            print(f"      Volume: {row['volume']:,} shares")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error in analysis: {e}")
        return False

if __name__ == "__main__":
    print("🎨 E2E NETWORKS DATA VISUALIZATION")
    print("=" * 40)
    
    # Install matplotlib if needed
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("📦 Installing matplotlib...")
        import subprocess
        subprocess.run(["pip", "install", "matplotlib"], check=True)
        import matplotlib.pyplot as plt
    
    # Create visualization
    if create_price_chart():
        print("✅ Visualization created successfully!")
    
    # Analyze recent performance
    analyze_recent_performance()
    
    print("🎉 Analysis Complete!")
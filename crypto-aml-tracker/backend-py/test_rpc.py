#!/usr/bin/env python3
"""Quick test to verify RPC and balance fetching works"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.balance_aggregator import get_aggregator
from db.mysql import connect_mysql, close_mysql


async def test_balance_fetch():
    """Test fetching balance for a known address with funds"""
    
    # Vitalik's address (known to have ETH)
    test_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    
    print("=" * 60)
    print("Testing Balance Aggregator")
    print("=" * 60)
    
    await connect_mysql()
    
    try:
        aggregator = get_aggregator()
        
        print(f"\n1. Testing ETH balance fetch for Vitalik's address...")
        eth_balance = await aggregator.fetch_eth_balance(test_address)
        print(f"   Result: {eth_balance} ETH")
        
        if eth_balance > 0:
            print("   ✅ RPC is working!")
        else:
            print("   ⚠️  Got 0 balance - RPC might not be working")
        
        print(f"\n2. Testing token price fetch...")
        prices = await aggregator.fetch_token_prices()
        print(f"   ETH price: ${prices.get('ETH', 0)}")
        print(f"   USDT price: ${prices.get('USDT', 0)}")
        
        if prices.get('ETH', 0) > 0:
            print("   ✅ CoinGecko API is working!")
        else:
            print("   ⚠️  Got $0 price - CoinGecko might not be working")
        
        print(f"\n3. Testing full balance update...")
        await aggregator.update_address(test_address)
        
        print("\n" + "=" * 60)
        print("Test complete! Check the output above for any errors.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await close_mysql()


if __name__ == "__main__":
    asyncio.run(test_balance_fetch())

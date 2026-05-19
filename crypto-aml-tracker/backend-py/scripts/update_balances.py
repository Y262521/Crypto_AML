#!/usr/bin/env python3
"""
Manual script to update balances for testing MVA functionality.
Usage: python scripts/update_balances.py <cluster_id_or_address>
"""

import sys
import asyncio
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.balance_aggregator import get_aggregator
from db.mysql import connect_mysql, close_mysql, fetch_one
import aiomysql


async def update_entity_balances(entity_id: str):
    """Update balances for an address or cluster."""
    await connect_mysql()
    
    try:
        aggregator = get_aggregator()
        
        # Check if it's a cluster or address
        # Try to find it in clusters first
        from db.mysql import get_pool
        pool = get_pool()
        
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # Check if it's a cluster
                await cur.execute(
                    "SELECT cluster_id, addresses FROM address_clusters WHERE cluster_id = %s LIMIT 1",
                    (entity_id,)
                )
                cluster = await cur.fetchone()
                
                if cluster:
                    # It's a cluster
                    import json
                    addresses = json.loads(cluster['addresses']) if cluster['addresses'] else []
                    print(f"Found cluster {entity_id} with {len(addresses)} addresses")
                    print(f"Updating balances for cluster...")
                    await aggregator.update_cluster(entity_id, addresses)
                    print(f"✓ Successfully updated cluster {entity_id}")
                else:
                    # Assume it's an address
                    print(f"Treating {entity_id} as an address")
                    print(f"Fetching balances...")
                    await aggregator.update_address(entity_id)
                    print(f"✓ Successfully updated address {entity_id}")
    
    except Exception as e:
        print(f"Error updating balances: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await close_mysql()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_balances.py <cluster_id_or_address>")
        print("\nExample:")
        print("  python scripts/update_balances.py 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        print("  python scripts/update_balances.py cluster_123")
        sys.exit(1)
    
    entity_id = sys.argv[1]
    await update_entity_balances(entity_id)


if __name__ == "__main__":
    asyncio.run(main())

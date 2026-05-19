#!/bin/bash
# Quick test to verify RPC is working

echo "Testing Alchemy RPC..."
curl -X POST https://eth-mainnet.g.alchemy.com/v2/demo \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_getBalance",
    "params": ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "latest"],
    "id": 1
  }' 2>/dev/null | python3 -m json.tool

echo ""
echo "If you see a 'result' with a hex number, RPC is working!"
echo "If you see an error, the RPC key is invalid."

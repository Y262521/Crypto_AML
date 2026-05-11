from __future__ import annotations

PROTOCOL_REGISTRY: dict[str, dict[str, set[str]]] = {
    "ethereum": {
        "uniswap": {
            "0x7a250d5630b4cf539739df2c5dacab4c659f2488",
        },
        "aave": {
            "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",
        },
        "curve": {
            "0xd51a44d3fae010294c616388b506acda1bfaae46",
        },
        "wormhole": {
            "0x3ee18b2214aff97000d974cf647e7c347e8fa585",
        },
        "layerzero": {
            "0x66a71dcef29a0ffbdbe3c6a460a3b5bc225cd675",
        },
        "tornado_cash": {
            "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b",
        },
    },
    "bsc": {
        "pancakeswap": {
            "0x10ed43c718714eb63d5aa57b78b54704e256024e",
        },
        "layerzero": {
            "0x3c2269811836af69497e5f486a85d7316753cf62",
        },
    },
    "polygon": {
        "quickswap": {
            "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff",
        },
        "aave": {
            "0x8dff5e27ea6b7ac08ebfdf9eb090f32ee9a30fcf",
        },
    },
    "arbitrum": {
        "uniswap": {
            "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",
        },
        "gmx": {
            "0xa906f338cb21815cbc4bc87ace9e68c87ef8d8f1",
        },
    },
}


def get_protocol_registry(chain: str) -> dict[str, set[str]]:
    return PROTOCOL_REGISTRY.get(chain, {})

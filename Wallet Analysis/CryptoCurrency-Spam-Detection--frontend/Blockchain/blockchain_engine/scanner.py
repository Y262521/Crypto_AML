from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from blockchain_engine.alerts import AlertEngine
from blockchain_engine.config import ScannerConfig
from blockchain_engine.connectors import BitcoinConnector, EVMConnector
from blockchain_engine.connectors.solana import SolanaConnector
from blockchain_engine.detectors import classify_entity, detect_activity, label_transactions
from blockchain_engine.explorer import ExplorerService
from blockchain_engine.graph_analysis import GraphAnalyzer
from blockchain_engine.indexer import SqliteIndexer
from blockchain_engine.models import RiskResult, ScreeningMatch, ScreeningResult
from blockchain_engine.network import RetryConfig
from blockchain_engine.public_feeds import PublicFeedSync
from blockchain_engine.risk_engine import RiskEngine
from blockchain_engine.watchlist import WatchlistManager


class BlockchainScanner:
    def __init__(self, config: ScannerConfig | None = None) -> None:
        self.config = config or ScannerConfig()
        self.config.ensure_data_dir()
        retry_config = RetryConfig(
            attempts=self.config.request_retries,
            backoff_seconds=self.config.request_backoff_seconds,
        )
        self.connectors = {
            "ethereum": EVMConnector(
                chain="ethereum",
                rpc_url=self.config.ethereum_rpc_url,
                request_timeout=self.config.request_timeout,
                explorer_api_url=self.config.ethereum_explorer_api_url,
                explorer_api_key=self.config.explorer_api_key,
                blockscout_api_url=self.config.ethereum_blockscout_api_url,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "bsc": EVMConnector(
                chain="bsc",
                rpc_url=self.config.bsc_rpc_url,
                request_timeout=self.config.request_timeout,
                explorer_api_url=self.config.bsc_explorer_api_url,
                explorer_api_key=self.config.explorer_api_key,
                blockscout_api_url=self.config.bsc_blockscout_api_url,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "polygon": EVMConnector(
                chain="polygon",
                rpc_url=self.config.polygon_rpc_url,
                request_timeout=self.config.request_timeout,
                explorer_api_url=self.config.polygon_explorer_api_url,
                explorer_api_key=self.config.explorer_api_key,
                blockscout_api_url=self.config.polygon_blockscout_api_url,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "arbitrum": EVMConnector(
                chain="arbitrum",
                rpc_url=self.config.arbitrum_rpc_url,
                request_timeout=self.config.request_timeout,
                explorer_api_url=self.config.arbitrum_explorer_api_url,
                explorer_api_key=self.config.explorer_api_key,
                blockscout_api_url=self.config.arbitrum_blockscout_api_url,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "bitcoin": BitcoinConnector(
                api_url=self.config.bitcoin_api_url,
                request_timeout=self.config.request_timeout,
                retry_config=retry_config,
            ),
            "sepolia": EVMConnector(
                chain="sepolia",
                rpc_url=self.config.sepolia_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "optimism": EVMConnector(
                chain="optimism",
                rpc_url=self.config.optimism_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "avalanche": EVMConnector(
                chain="avalanche",
                rpc_url=self.config.avalanche_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "fantom": EVMConnector(
                chain="fantom",
                rpc_url=self.config.fantom_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "base": EVMConnector(
                chain="base",
                rpc_url=self.config.base_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "celo": EVMConnector(
                chain="celo",
                rpc_url=self.config.celo_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "gnosis": EVMConnector(
                chain="gnosis",
                rpc_url=self.config.gnosis_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "cronos": EVMConnector(
                chain="cronos",
                rpc_url=self.config.cronos_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "moonbeam": EVMConnector(
                chain="moonbeam",
                rpc_url=self.config.moonbeam_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "metis": EVMConnector(
                chain="metis",
                rpc_url=self.config.metis_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "kava": EVMConnector(
                chain="kava",
                rpc_url=self.config.kava_rpc_url,
                request_timeout=self.config.request_timeout,
                max_rpc_scan_blocks=self.config.max_rpc_scan_blocks,
                retry_config=retry_config,
            ),
            "solana": SolanaConnector(
                api_url=self.config.solana_api_url,
                request_timeout=self.config.request_timeout,
                retry_config=retry_config,
            ),
        }
        self.indexer = SqliteIndexer(self.config.data_dir)
        self.risk_engine = RiskEngine(self.config.data_dir)
        self.feed_sync = PublicFeedSync(self.config.data_dir, self.config.request_timeout)
        self.watchlist = WatchlistManager(self.config.data_dir)
        self.explorer = ExplorerService(self.indexer)
        self.graph_analyzer = GraphAnalyzer()
        self.alert_engine = AlertEngine(self.config.data_dir)

    def sync_public_feeds(self) -> dict[str, int]:
        return self.feed_sync.sync_all()

    def scan_address(self, chain: str, address: str, limit: int = 50) -> RiskResult:
        connector = self.connectors[chain]
        transactions = connector.get_transactions(address=address, limit=limit)
        
        # Label transactions (send, swap, buy, receive)
        label_transactions(transactions, address)
        
        detections = detect_activity(transactions)
        
        # New entity labeling logic
        bytecode = connector.get_code(address)
        entity_label = classify_entity(
            address=address,
            transactions=transactions,
            detections=detections,
            bytecode=bytecode,
        )

        self.indexer.append(transactions)
        result = self.risk_engine.evaluate(
            chain=chain,
            address=address,
            transactions=transactions,
            detections=detections,
            entity_label=entity_label,
        )
        return result

    def scan_cross_chain(self, addresses: dict[str, str], limit: int = 25) -> dict[str, RiskResult]:
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(addresses)))) as executor:
            futures = {
                chain: executor.submit(self.scan_address, chain=chain, address=address, limit=limit)
                for chain, address in addresses.items()
            }
            results: dict[str, RiskResult] = {}
            errors: dict[str, str] = {}
            for chain, future in futures.items():
                try:
                    results[chain] = future.result()
                except Exception as exc:
                    errors[chain] = str(exc)
            if errors and not results:
                raise RuntimeError(f"Cross-chain scan failed: {errors}")
            return results

    def get_balance(self, chain: str, address: str) -> dict:
        return self.connectors[chain].get_balance(address)

    def get_token_transfers(
        self,
        chain: str,
        address: str,
        from_block: str = "0x0",
        to_block: str = "latest",
    ) -> list[dict]:
        connector = self.connectors[chain]
        if not hasattr(connector, "get_token_transfers"):
            raise ValueError(f"Token transfers are not supported for chain '{chain}'")
        return connector.get_token_transfers(address, from_block=from_block, to_block=to_block)

    def get_chain_health(self) -> dict[str, str]:
        status: dict[str, str] = {}
        for chain, connector in self.connectors.items():
            try:
                if chain == "bitcoin":
                    connector.get_balance("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
                else:
                    connector.get_balance("0x0000000000000000000000000000000000000000")
                status[chain] = "ok"
            except Exception as exc:  # pragma: no cover - operational reporting
                status[chain] = f"error: {exc}"
        return status

    def screen_address(self, chain: str, address: str) -> ScreeningResult:
        flagged_db = self.risk_engine._load_flagged_db()
        address_key = address.lower()
        matches = [
            ScreeningMatch(
                address=record["address"],
                category=record["category"],
                source=record["source"],
                score=int(record.get("score", 60)),
                label=record.get("label"),
            )
            for record in flagged_db.get(chain, []) + flagged_db.get("global", [])
            if record["address"].lower() == address_key
        ]
        
        # Add entity labeling to screening
        connector = self.connectors[chain]
        bytecode = connector.get_code(address)
        # print(f"DEBUG: address={address} bytecode_len={len(bytecode)}")

        entity_label = classify_entity(
            address=address,
            transactions=[], # Empty for quick screen
            detections=[], # Empty for quick screen
            bytecode=bytecode,
        )

        return ScreeningResult(
            address=address,
            chain=chain,
            matched=bool(matches),
            entity_label=entity_label,
            matches=matches,
        )

    def explore_address(self, chain: str, address: str, limit: int = 25) -> dict:
        # scan_address can fail on flaky public RPCs / explorer limits; still return balance + indexed rows
        try:
            self.scan_address(chain=chain, address=address, limit=limit)
        except Exception:
            pass
        try:
            balance_info = self.get_balance(chain, address)
            balance = balance_info.get("balance", 0.0)
        except Exception:
            balance = 0.0
        transactions = self.explorer.get_address_transactions(chain, address, limit=limit)
        return self.explorer.summarize_address(chain, address, balance, transactions)

    def explore_transaction(self, tx_hash: str) -> dict | None:
        return self.explorer.get_transaction(tx_hash)

    def build_graph(self, chain: str, address: str, limit: int = 25) -> dict:
        result = self.scan_address(chain=chain, address=address, limit=limit)
        transactions = self.explorer.get_address_transactions(chain, address, limit=limit)
        return self.graph_analyzer.build_graph(
            root_address=address,
            risk_score=result.score,
            label=result.label,
            entity_label=result.entity_label,
            transactions=transactions,
        )

    def cluster_address(self, chain: str, address: str, limit: int = 25) -> list[dict]:
        self.scan_address(chain=chain, address=address, limit=limit)
        transactions = self.explorer.get_address_transactions(chain, address, limit=limit)
        return self.graph_analyzer.cluster_addresses(transactions)

    def evaluate_alerts(self, chain: str, address: str, limit: int = 25) -> list[dict]:
        result = self.scan_address(chain=chain, address=address, limit=limit)
        watchlist_entries = [
            entry
            for entry in self.watchlist.list_entries()
            if entry["chain"] == chain and entry["address"].lower() == address.lower()
        ]
        transactions = self.explorer.get_address_transactions(chain, address, limit=limit)
        clusters = self.graph_analyzer.cluster_addresses(transactions)
        return self.alert_engine.evaluate(
            address=address,
            chain=chain,
            risk_score=result.score,
            risk_label=result.label,
            watchlist_entries=watchlist_entries,
            clusters=clusters,
            transactions=transactions,
        )

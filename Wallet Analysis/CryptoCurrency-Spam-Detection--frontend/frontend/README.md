## Crypto-Currency Scam Detection

Frontend for blockchain risk analytics integrated with the NestJS backend.

## Architecture

- `src/pages` contains feature pages (Dashboard, Graph, Watchlist, Alerts, Batch, Audit, etc.).
- `src/components` contains reusable UI panels (risk, graph, dapps, anomalies, mev, cross-chain, screening, clustering).
- `src/lib/endpoints.ts` is the API layer for backend integration.
- Dashboard is the main analyst workspace:
  - wallet screening + entity labeling
  - summary + transaction explorer
  - risk scoring + factors
  - graph, analytics, dapps, anomalies, cross-chain, mev, clustering tabs

## Feature Coverage

- Wallet/address screening with category-based matches and source labels.
- Address and transaction explorer with filtering, pagination, and chain selection.
- Risk scoring display with explanations and severity.
- Graph visualization with hop depth and filters.
- Address clustering panel with inferred relations and cluster scores.
- Watchlist management with add/update/remove and alerts toggles.
- Alerts and monitoring UI + settings.
- API-first integration for external access through backend endpoints.

## Assumptions

- Backend is running and reachable via `VITE_API_URL`.
- Backend endpoints under `/api/v1/*` are available.
- Optional Moralis integrations are enabled on backend (`MORALIS_API_KEY`) for richer DeFi/approval data.
- Data quality depends on indexed transactions and watchlist curation in backend DB.

## Limitations

- Screening/entity labels are heuristic + curated-source dependent (not full forensic attribution).
- Clustering is simplified behavioral inference and not deterministic ownership proof.
- Some advanced analytics (MEV/anomalies/cross-chain) are still incremental and improve as indexed data grows.
- Real-time websocket alerts depend on backend websocket configuration.

## Run

```bash
npm install
npm run dev
```


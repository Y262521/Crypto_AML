#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Database Shutdown Script
# ═══════════════════════════════════════════════════════════════════════════

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "  Stopping All Databases"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Stop PostgreSQL & Redis
log_info "Stopping PostgreSQL and Redis..."
cd "$ROOT/CryptoCurrency-Spam-Detection--frontend/backend"
docker-compose down
cd "$ROOT"
log_success "PostgreSQL and Redis stopped"

# Stop MongoDB
log_info "Stopping MongoDB..."
docker stop aml-mongodb >/dev/null 2>&1 || true
log_success "MongoDB stopped"

# Stop MySQL
log_info "Stopping MySQL..."
docker stop aml-mysql >/dev/null 2>&1 || true
log_success "MySQL stopped"

# Stop Neo4j
log_info "Stopping Neo4j..."
docker stop aml-neo4j >/dev/null 2>&1 || true
log_success "Neo4j stopped"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ All databases stopped!${NC}"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
log_info "To start databases again, run: ./start-databases.sh"
echo ""

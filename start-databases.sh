#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Database Startup Script
# ═══════════════════════════════════════════════════════════════════════════
# Starts all required databases for the Crypto Intelligence Platform:
#   - MongoDB (Port 27017) — AML Backend
#   - MySQL/MariaDB (Port 3306) — AML Backend
#   - Neo4j (Port 7687, 7474) — AML Backend
#   - PostgreSQL (Port 5433) — Wallet Analysis Backend
#   - Redis (Port 6379) — Wallet Analysis Backend
# ═══════════════════════════════════════════════════════════════════════════

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "  Database Startup Script"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker first."
    exit 1
fi

log_success "Docker is running"
echo ""

# ── Start PostgreSQL & Redis (Wallet Analysis) ────────────────────────────────
log_info "Starting PostgreSQL and Redis for Wallet Analysis..."
cd "$ROOT/CryptoCurrency-Spam-Detection--frontend/backend"
docker-compose up -d
cd "$ROOT"
log_success "PostgreSQL (port 5433) and Redis (port 6379) started"

# ── Start MongoDB (AML) ───────────────────────────────────────────────────────
log_info "Starting MongoDB for AML..."
if docker ps -a --format '{{.Names}}' | grep -q '^aml-mongodb$'; then
    docker start aml-mongodb >/dev/null 2>&1 || true
    log_success "MongoDB container started (existing)"
else
    docker run -d \
        --name aml-mongodb \
        -p 27017:27017 \
        -v aml-mongodb-data:/data/db \
        mongo:latest >/dev/null 2>&1
    log_success "MongoDB container created and started (port 27017)"
fi

# ── Start MySQL/MariaDB (AML) ─────────────────────────────────────────────────
log_info "Starting MySQL/MariaDB for AML..."
if docker ps -a --format '{{.Names}}' | grep -q '^aml-mysql$'; then
    docker start aml-mysql >/dev/null 2>&1 || true
    log_success "MySQL container started (existing)"
else
    docker run -d \
        --name aml-mysql \
        -p 3306:3306 \
        -e MYSQL_ROOT_PASSWORD=hakim22 \
        -e MYSQL_USER=hakim \
        -e MYSQL_PASSWORD=hakim22 \
        -e MYSQL_DATABASE=aml_clean \
        -v aml-mysql-data:/var/lib/mysql \
        mysql:8.0 >/dev/null 2>&1
    log_success "MySQL container created and started (port 3306)"
fi

# ── Start Neo4j (AML) ─────────────────────────────────────────────────────────
log_info "Starting Neo4j for AML..."
if docker ps -a --format '{{.Names}}' | grep -q '^aml-neo4j$'; then
    docker start aml-neo4j >/dev/null 2>&1 || true
    log_success "Neo4j container started (existing)"
else
    docker run -d \
        --name aml-neo4j \
        -p 7474:7474 \
        -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/hakimaj22 \
        -v aml-neo4j-data:/data \
        neo4j:latest >/dev/null 2>&1
    log_success "Neo4j container created and started (ports 7474, 7687)"
fi

# ── Wait for databases to be ready ────────────────────────────────────────────
echo ""
log_info "Waiting for databases to be ready..."
sleep 5

# Check PostgreSQL
if docker exec crypto-postgres pg_isready -U postgres >/dev/null 2>&1; then
    log_success "PostgreSQL is ready"
else
    log_warn "PostgreSQL may still be starting up"
fi

# Check Redis
if docker exec crypto-redis redis-cli ping >/dev/null 2>&1; then
    log_success "Redis is ready"
else
    log_warn "Redis may still be starting up"
fi

# Check MongoDB
if docker exec aml-mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    log_success "MongoDB is ready"
else
    log_warn "MongoDB may still be starting up"
fi

# Check MySQL
if docker exec aml-mysql mysqladmin ping -h localhost -u root -phakim22 >/dev/null 2>&1; then
    log_success "MySQL is ready"
else
    log_warn "MySQL may still be starting up"
fi

# Check Neo4j (takes longer to start)
log_info "Neo4j may take 30-60 seconds to fully start..."

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ All databases started!${NC}"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "  Database Status:"
echo "    • MongoDB    → localhost:27017"
echo "    • MySQL      → localhost:3306"
echo "    • Neo4j      → localhost:7687 (Bolt), localhost:7474 (Browser)"
echo "    • PostgreSQL → localhost:5433"
echo "    • Redis      → localhost:6379"
echo ""
echo "  Neo4j Browser: http://localhost:7474"
echo "    Username: neo4j"
echo "    Password: hakimaj22"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
log_info "To stop all databases, run: ./stop-databases.sh"
echo ""

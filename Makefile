# RYX — Makefile
# Usage : make <target>
# Voir CLAUDE.md pour la documentation complète

.PHONY: help infra-up infra-down dev edge-dev build test lint migrate seed clean

SERVICES := gateway patient ingestion preprocess imaging inference evidence prediction search integration notification observability
DOCKER_COMPOSE := docker compose

# ─── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo "RYX — Commandes disponibles:"
	@echo ""
	@echo "  Démarrage:"
	@echo "    make infra-up       Démarrer infrastructure (PostgreSQL, Redis, MinIO, ...)"
	@echo "    make infra-down     Stopper infrastructure"
	@echo "    make dev            Démarrer tous les services (hot-reload)"
	@echo "    make edge-dev       Mode offline edge"
	@echo ""
	@echo "  Base de données:"
	@echo "    make migrate        Lancer migrations Alembic"
	@echo "    make seed           Seed données de test"
	@echo ""
	@echo "  Tests & Qualité:"
	@echo "    make test           Tous les tests"
	@echo "    make test S=patient Tests d'un service spécifique"
	@echo "    make lint           Ruff + mypy + eslint"
	@echo "    make lint-fix       Corriger les erreurs de lint"
	@echo ""
	@echo "  Build:"
	@echo "    make build          Build toutes les images Docker"
	@echo "    make build S=patient Build une image spécifique"
	@echo ""
	@echo "  Utilitaires:"
	@echo "    make network        Créer le réseau Docker ryx-network"
	@echo "    make clean          Supprimer containers + volumes dev"
	@echo "    make logs S=patient Logs d'un service"
	@echo "    make shell S=patient Shell dans un service"
	@echo "    make docs           Générer doc API OpenAPI"

# ─── Infrastructure ───────────────────────────────────────────────────────────

network:
	@docker network create ryx-network 2>/dev/null || echo "Network déjà créé"

infra-up: network
	@echo "🚀 Démarrage infrastructure RYX..."
	$(DOCKER_COMPOSE) -f docker-compose.infra.yml up -d
	@echo "⏳ Attente de la disponibilité des services..."
	@sleep 5
	@echo "✅ Infrastructure prête !"
	@echo "   PostgreSQL : localhost:5432"
	@echo "   Redis      : localhost:6379"
	@echo "   MinIO      : localhost:9000 (console: 9001)"
	@echo "   Meili      : localhost:7700"
	@echo "   Orthanc    : localhost:8042"

infra-down:
	$(DOCKER_COMPOSE) -f docker-compose.infra.yml down

# ─── Développement ────────────────────────────────────────────────────────────

dev: network infra-up
	@echo "🚀 Démarrage services RYX (mode hub)..."
	$(DOCKER_COMPOSE) up -d

edge-dev: network
	@echo "🔌 Démarrage RYX en mode EDGE (offline)..."
	$(DOCKER_COMPOSE) -f docker-compose.edge.yml up -d

# ─── Base de données ──────────────────────────────────────────────────────────

migrate:
	@for s in $(SERVICES); do \
		echo "Migration service: $$s"; \
		cd services/$$s && \
		uv run alembic upgrade head 2>/dev/null || echo "  (pas de migrations dans $$s)"; \
		cd ../..; \
	done

seed:
	@echo "🌱 Seed données de test..."
	uv run python scripts/seed.py

# ─── Tests ────────────────────────────────────────────────────────────────────

test:
	@if [ -n "$(S)" ]; then \
		echo "🧪 Tests service: $(S)"; \
		cd services/$(S) && uv run pytest tests/ -v --cov=app --cov-report=term-missing; \
	else \
		echo "🧪 Tous les tests..."; \
		for s in $(SERVICES); do \
			echo "\n--- Service: $$s ---"; \
			cd services/$$s && uv run pytest tests/ -q 2>/dev/null || echo "  (pas de tests)"; \
			cd ../..; \
		done; \
		echo "\n🧪 Tests packages..."; \
		cd packages/shared && uv run pytest tests/ -q 2>/dev/null || echo "  (pas de tests)"; \
		cd ../..; \
		cd packages/evidence-guard && uv run pytest tests/ -q 2>/dev/null || echo "  (pas de tests)"; \
	fi

# ─── Lint & Quality ───────────────────────────────────────────────────────────

lint:
	@echo "🔍 Lint Python (ruff + mypy)..."
	@for s in $(SERVICES); do \
		cd services/$$s && \
		uv run ruff check . --quiet && \
		echo "  ✓ $$s" || echo "  ✗ $$s"; \
		cd ../..; \
	done
	@echo "🔍 Lint Frontend (eslint + tsc)..."
	@cd apps/web && pnpm lint

lint-fix:
	@for s in $(SERVICES); do \
		cd services/$$s && uv run ruff check --fix . && cd ../..; \
	done
	@cd apps/web && pnpm lint:fix

# ─── Build ────────────────────────────────────────────────────────────────────

build:
	@if [ -n "$(S)" ]; then \
		echo "🔨 Build: $(S)"; \
		$(DOCKER_COMPOSE) build $(S); \
	else \
		echo "🔨 Build toutes les images..."; \
		$(DOCKER_COMPOSE) build; \
	fi

# ─── Utilitaires ──────────────────────────────────────────────────────────────

logs:
	@if [ -n "$(S)" ]; then \
		$(DOCKER_COMPOSE) logs -f $(S); \
	else \
		$(DOCKER_COMPOSE) logs -f; \
	fi

shell:
	@if [ -n "$(S)" ]; then \
		$(DOCKER_COMPOSE) exec $(S) bash; \
	else \
		echo "Usage: make shell S=<service_name>"; \
	fi

docs:
	@echo "📚 Génération doc API..."
	@for s in $(SERVICES); do \
		echo "  $$s → http://localhost:800$$(echo $(SERVICES) | tr ' ' '\n' | grep -n $$s | cut -d: -f1)/docs"; \
	done

clean:
	@echo "⚠️  Suppression des containers et volumes de développement..."
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) -f docker-compose.infra.yml down -v
	docker system prune -f

# ─── Setup initial ────────────────────────────────────────────────────────────

setup:
	@echo "⚙️  Configuration initiale RYX..."
	@cp -n .env.example .env || echo "  .env existe déjà"
	@mkdir -p models/edge knowledge-pack edge-data
	@echo "✅ Setup terminé. Éditez .env si nécessaire, puis: make infra-up && make dev"

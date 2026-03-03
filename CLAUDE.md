# CLAUDE.md — RYX (Clinical AI Layer)

> Ce fichier est lu par Claude Code en premier. Il contient tout ce dont tu as besoin pour vibecoder ce projet efficacement.

---

## 0. Contexte projet

**RYX** est une couche IA clinique destinée aux hôpitaux, principalement en RDC (Congo). C'est un système **offline-first**, **evidence-first**, **interop-first**.

Philosophie : RYX n'est pas un médecin. C'est un filet de sécurité, un organisateur de dossier, un assistant de raisonnement, un outil d'apprentissage.

---

## 1. Structure du monorepo

```
ryx/
├── apps/web/             # Dashboard Next.js (TypeScript)
├── services/             # Microservices backend (Python/FastAPI)
│   ├── gateway/          # Auth, RBAC, Audit
│   ├── patient/          # Mini-DMI (patients, encounters)
│   ├── ingestion/        # Upload docs, DICOM, connecteurs
│   ├── preprocess/       # OCR, nettoyage, extraction structurée
│   ├── imaging/          # Stockage DICOM + viewer endpoints
│   ├── inference/        # Pillar-0 + MedGemma runners
│   ├── evidence/         # EvidenceGuard + EvidenceRefs
│   ├── prediction/       # Plugins prédiction longitudinale
│   ├── search/           # Index patient + Knowledge Pack
│   ├── integration/      # Connector SDK + DMI sync
│   ├── notification/     # Dashboard + WhatsApp (no PHI)
│   └── observability/    # Metrics, logs, tracing
├── packages/
│   ├── shared/           # Types Pydantic partagés, events, schemas
│   ├── evidence-guard/   # Policy engine (lib partagée)
│   └── connector-sdk/    # SDK connecteurs DMI
├── infra/
│   ├── docker/           # Dockerfiles
│   ├── k8s/              # Manifests Kubernetes
│   └── helm/             # Helm charts
├── docs/                 # Architecture, ADR, API specs
└── scripts/              # Dev scripts, seeds, migrations
```

---

## 2. Stack technique

### Backend (services/)
- **Runtime**: Python 3.12
- **Framework**: FastAPI + Uvicorn
- **Validation**: Pydantic v2
- **ORM**: SQLAlchemy 2.0 (async) + Alembic (migrations)
- **Event Bus**: Redis Streams (MVP)
- **Package manager**: `uv` (moderne, rapide)

### Frontend (apps/web/)
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript strict
- **UI**: Tailwind CSS + shadcn/ui
- **State**: Zustand (global) + TanStack Query (server state)
- **Package manager**: pnpm

### Bases de données
- **PostgreSQL 16**: données relationnelles (patients, encounters, labs, jobs)
- **Redis 7**: cache + event bus (streams) + sessions
- **MinIO**: stockage objets (PDFs, images, overlays DICOM)
- **Meilisearch**: index de recherche (patients + Knowledge Pack, offline-friendly)

### DICOM
- **Orthanc**: serveur DICOM open-source (sidecar)
- **OHIF Viewer**: viewer DICOM browser (intégré dans web)

### AI/ML
- **ONNX Runtime**: exécution edge (modèles quantisés)
- **HuggingFace Transformers**: hub (modèles complets)
- **EasyOCR / PaddleOCR**: OCR multilingue
- **Pillar-0**: modèle vision 3D CT/MRI
- **MedGemma 1.5**: raisonnement clinique

### Infra
- **Docker + Docker Compose**: dev local
- **Kubernetes + Helm**: production hub
- **Prometheus + Grafana**: métriques
- **OpenTelemetry**: tracing distribué

---

## 3. Conventions de code

### Python (services + packages)
```python
# Nommage
snake_case pour variables, fonctions, modules
PascalCase pour classes et modèles Pydantic
UPPER_CASE pour constantes

# Modèles Pydantic
class PatientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    ...

# Routes FastAPI
@router.post("/patients", response_model=PatientResponse, status_code=201)
async def create_patient(body: PatientCreate, db: AsyncSession = Depends(get_db)):
    ...

# Toujours async pour les handlers
# Toujours typer les retours
# Jamais de print() → utiliser structlog ou loguru
```

### TypeScript (apps/web)
```typescript
// Nommage
camelCase pour variables et fonctions
PascalCase pour composants, types, interfaces
kebab-case pour les fichiers de composants

// Types explicites, jamais de `any`
// Composants : préférer fonction fléchée + export default
// API calls via lib/api.ts (centralisé)
```

### Commits
```
<type>(<scope>): <description courte>

Types : feat | fix | chore | docs | refactor | test | ci
Scopes : gateway | patient | ingestion | preprocess | imaging | inference | evidence | prediction | search | integration | notification | web | shared | infra

Exemples :
feat(patient): add mini-DMI CRUD endpoints
fix(evidence): block claim without evidence_refs
docs(adr): add ADR-003 redis-streams choice
```

---

## 4. Règles métier critiques (à ne JAMAIS violer)

### EvidenceGuard
```python
# TOUTE recommandation, alerte, score, diagnostic, traitement DOIT avoir evidence_refs
# Si evidence_refs vide → status = "blocked", event "evidence.blocked" publié
# "Better empty than wrong"

class Claim(BaseModel):
    claim_id: UUID
    type: ClaimType  # reco | alert | score | dx | tx | info
    text: str
    criticality: CriticalityLevel
    evidence_refs: list[EvidenceRef]  # DOIT être non-vide
    status: ClaimStatus  # pending | valid | blocked | needs_human
```

### PHI (Protected Health Information)
- JAMAIS de PHI dans WhatsApp / notifications externes
- WhatsApp = token de cas anonyme + lien sécurisé vers dashboard
- Tout accès patient → audit log obligatoire

### Offline-first
- Toujours vérifier si la fonction est requise en mode edge avant d'ajouter une dépendance externe
- Les jobs hub → sérialisés dans JobQueue locale → sync quand connectivité

---

## 5. Développement local

### Démarrage rapide
```bash
# 1. Copier les variables d'environnement
cp .env.example .env

# 2. Démarrer l'infrastructure
make infra-up

# 3. Démarrer tous les services
make dev

# 4. Démarrer en mode edge (offline)
make edge-dev
```

### Commandes Make
```bash
make infra-up        # Lance PostgreSQL, Redis, MinIO, Meilisearch, Orthanc
make infra-down      # Stoppe l'infrastructure
make dev             # Lance tous les services en mode dev (avec hot-reload)
make edge-dev        # Mode offline edge
make migrate         # Lance les migrations Alembic
make seed            # Seed données de test
make test            # Tous les tests
make test-service S=patient  # Tests d'un service
make lint            # Ruff + mypy + eslint
make build           # Build Docker images
make docs            # Génère la doc API (OpenAPI)
```

### Variables d'environnement importantes
```env
# Obligatoires
DATABASE_URL=postgresql+asyncpg://ryx:ryx@localhost:5432/ryx
REDIS_URL=redis://localhost:6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=ryxdev
MINIO_SECRET_KEY=ryxdev123

# Mode déploiement
RYX_MODE=hub  # ou "edge"
RYX_ENV=development  # ou "production"

# Auth
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256

# WhatsApp
WHATSAPP_API_TOKEN=  # Meta ou Twilio
WHATSAPP_PHONE_ID=

# IA
MEDGEMMA_MODEL_PATH=/models/medgemma-1.5
PILLAR0_MODEL_PATH=/models/pillar-0
ONNX_EDGE_MODEL_PATH=/models/edge/
```

---

## 6. Architecture des agents (rappel pour vibecoding)

Tous les agents tournent en continu, consomment des events Redis Streams, sont idempotents.

### Ordre du pipeline
```
IngestionAgent
  → PreprocessAgent / ImagingImportAgent
  → MedGemmaAgent + Pillar0Agent (parallel)
  → PredictionAgent
  → EvidenceGuardAgent
  → IndexerAgent
  → NotificationAgent
```

### Pattern agent (à suivre)
```python
# services/<service>/app/agents/<agent_name>.py
class MyAgent:
    def __init__(self, redis: Redis, db: AsyncSession, ...):
        self.redis = redis
        self.consumer_group = "my-agent-group"
        self.stream_key = "my-event-stream"

    async def run(self):
        """Loop principal 24/7"""
        await self._ensure_consumer_group()
        while True:
            messages = await self.redis.xreadgroup(...)
            for msg in messages:
                await self._process(msg)

    async def _process(self, msg):
        """Idempotent, avec retry"""
        ...
```

---

## 7. Tests

### Structure
```
services/<service>/
├── tests/
│   ├── unit/         # Tests unitaires (pas d'I/O)
│   ├── integration/  # Tests avec DB/Redis (fixtures pytest)
│   └── e2e/          # Tests end-to-end (docker-compose test)
```

### Fixtures importantes
```python
# conftest.py
@pytest.fixture
async def db_session(): ...  # Session DB de test
@pytest.fixture
async def redis_client(): ...  # Redis de test
@pytest.fixture
def evidence_guard(): ...  # EvidenceGuard policy engine
```

### Règles
- Tout endpoint → au moins 1 test d'intégration
- EvidenceGuard → tests unitaires exhaustifs (c'est le coeur de la sécurité)
- Agents → tests avec Redis mock
- Couverture minimale : 70%

---

## 8. Sécurité (checklist avant PR)

- [ ] Aucune PHI dans les logs
- [ ] Aucune PHI dans les messages WhatsApp
- [ ] Tous les claims ont des `evidence_refs`
- [ ] Tous les endpoints auth ont un middleware d'audit
- [ ] Input validation via Pydantic (jamais de validation manuelle)
- [ ] Pas de SQL brut (toujours SQLAlchemy ORM ou paramétrisé)
- [ ] Secrets en variables d'environnement uniquement (jamais hardcodés)

---

## 9. Glossaire métier

| Terme | Définition |
|-------|------------|
| **Claim** | Toute assertion RYX (reco, alerte, score, dx, tx) — doit être prouvée |
| **EvidenceRef** | Référence cliquable vers preuve (PDF bbox, DICOM slice, lab valeur, citation) |
| **EvidenceGuard** | Policy engine qui bloque les claims sans preuve |
| **Mini-DMI** | Dossier médical informatisé minimal intégré à RYX |
| **Knowledge Pack** | Bibliothèque médicale offline (guidelines, protocoles, references) |
| **Edge** | Mode offline (hôpital sans internet) |
| **Hub** | Mode cloud/serveur central |
| **Store & Forward** | Jobs mis en queue locale pour sync ultérieure |
| **Shadow mode** | Lecture seule sur DMI existant (pas d'écriture) |
| **Write-back** | RYX pousse rapports/alertes vers DMI externe |
| **PHI** | Protected Health Information (données sensibles patient) |
| **RBAC** | Role-Based Access Control |

---

## 10. Ressources

- PRD complet : `docs/PRD.md`
- Architecture : `docs/ARCHITECTURE.md`
- ADRs : `docs/adr/`
- API specs : `docs/api-contracts.md`
- Data model : `docs/data-model.md`
- Agents design : `docs/agents.md`

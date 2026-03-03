# RYX — Stack Technique

> Toutes les décisions techniques avec justification.

---

## Backend

| Composant | Technologie | Version | Raison |
|-----------|-------------|---------|--------|
| Runtime | Python | 3.12 | Écosystème ML, async natif |
| Framework | FastAPI | 0.115+ | DX excellent, OpenAPI auto, async |
| Validation | Pydantic | v2 | Performance, type safety |
| ORM | SQLAlchemy | 2.0 (async) | Async-first, mature |
| Migrations | Alembic | 1.13+ | Intégré SQLAlchemy |
| Package manager | uv | latest | 100x plus rapide que pip |
| HTTP client | httpx | 0.27+ | Async, compatible FastAPI |
| Logging | structlog | 24+ | JSON structuré, sans PHI |
| Task background | anyio | 4+ | Async concurrence |

## Frontend

| Composant | Technologie | Version | Raison |
|-----------|-------------|---------|--------|
| Framework | Next.js | 14+ (App Router) | SSR, routing, DX |
| Language | TypeScript | 5+ | Type safety strict |
| UI Kit | shadcn/ui | latest | Accessible, customizable |
| Styles | Tailwind CSS | 3.4+ | Rapide à prototyper |
| State global | Zustand | 4+ | Simple, léger |
| Server state | TanStack Query | 5+ | Cache, invalidation |
| Forms | React Hook Form + Zod | latest | Validation côté client |
| DICOM Viewer | OHIF Viewer | 3+ | Open source, browser |
| Websocket | native browser API | - | Notifications temps réel |
| Package manager | pnpm | 9+ | Rapide, disk efficient |

## Bases de données

| Composant | Technologie | Mode | Raison |
|-----------|-------------|------|--------|
| SQL principal | PostgreSQL | 16+ | Hub + Edge (peut être SQLite en edge) |
| Cache + Queue | Redis | 7+ | Streams (event bus), sessions, cache |
| Object Storage | MinIO | latest | S3-compatible, self-hosted, offline |
| Recherche | Meilisearch | 1.7+ | Offline-first, rapide, facile à embed |
| DICOM | Orthanc | 1.12+ | Open-source DICOM server, REST API |
| Edge DB | SQLite | 3.45+ | Mini-DMI edge (quand PostgreSQL non dispo) |

## AI/ML

| Composant | Technologie | Mode | Raison |
|-----------|-------------|------|--------|
| Vision 3D | Pillar-0 | Hub + Edge GPU | CT/MRI analysis |
| Raisonnement | MedGemma 1.5 | Hub (full) + Edge (ONNX quant) | Clinical AI |
| OCR | EasyOCR | Edge + Hub | Multilingue, offline |
| OCR fallback | Tesseract | Edge | Ultra-léger |
| Inference edge | ONNX Runtime | Edge | Quantized models (int8/int4) |
| Inference hub | HuggingFace Transformers | Hub | Full precision models |
| Image processing | OpenCV + Pillow | Edge + Hub | Preprocessing pipeline |
| PDF processing | PyMuPDF | Edge + Hub | Extraction, rendering |

## Infrastructure

| Composant | Technologie | Version | Raison |
|-----------|-------------|---------|--------|
| Containers | Docker | 25+ | Standard de facto |
| Dev orchestration | Docker Compose | v2 | Dev local multi-services |
| Prod orchestration | Kubernetes | 1.29+ | Scale, reliability |
| Helm charts | Helm | 3+ | Package Kubernetes |
| CI/CD | GitHub Actions | - | Intégré GitHub |
| Metrics | Prometheus | 2.50+ | Standard de facto |
| Dashboards | Grafana | 10+ | Visualisation metrics |
| Tracing | OpenTelemetry | latest | Distribué, standard CNCF |
| Logs collection | Loki | 2.9+ | Lightweight, Grafana intégré |

## Communication

| Composant | Technologie | Raison |
|-----------|-------------|--------|
| WhatsApp | Meta Cloud API | Business API officielle |
| WhatsApp alt | Twilio | Fallback / multi-pays |
| Temps réel | WebSocket (FastAPI) | Notifications dashboard |
| Email (admin) | SMTP / Resend | Alertes ops |

## Sécurité

| Composant | Technologie | Raison |
|-----------|-------------|--------|
| Auth | JWT (access 15min + refresh 7j) | Stateless, scalable |
| OAuth2 | OAuth2 flows (FastAPI) | Standards |
| RBAC | Custom (FastAPI middleware) | Granulaire par service |
| Secrets | Docker secrets / K8s secrets | Jamais hardcodés |
| TLS | Let's Encrypt / cert-manager | Chiffrement transit |
| Chiffrement at-rest | AES-256 (PostgreSQL + MinIO) | PHI protection |

---

## Matrice Offline/Hub

| Service | Edge (offline) | Hub (cloud) |
|---------|---------------|-------------|
| gateway | ✅ (local JWT) | ✅ |
| patient | ✅ (SQLite) | ✅ (PostgreSQL) |
| ingestion | ✅ | ✅ |
| preprocess | ✅ (EasyOCR local) | ✅ |
| imaging | ✅ (Orthanc local) | ✅ |
| inference (Pillar-0) | ⚡ (si GPU edge) | ✅ |
| inference (MedGemma) | ✅ (ONNX quant) | ✅ (full) |
| evidence | ✅ | ✅ |
| prediction | ⚡ (modèles légers) | ✅ (full) |
| search | ✅ (Meilisearch local) | ✅ |
| integration | 🔄 (store&forward) | ✅ |
| notification | ✅ (dashboard local) | ✅ (+ WhatsApp) |
| observability | ✅ (local metrics) | ✅ (centralisé) |

✅ = natif | ⚡ = conditionnel | 🔄 = différé

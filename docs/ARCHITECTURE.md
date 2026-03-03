# RYX — Architecture Technique

> Version : 1.0.0 | Date : 2026-03-03 | Auteur : Architecture Team

---

## 1. Vue d'ensemble

RYX est une **couche IA clinique** conçue autour de trois piliers non-négociables :

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRINCIPES FONDATEURS                        │
├─────────────────┬──────────────────┬───────────────────────────┤
│  OFFLINE-FIRST  │  EVIDENCE-FIRST  │      INTEROP-FIRST        │
│                 │                  │                           │
│ Fonctions core  │ Tout claim doit  │ Connector SDK DMI         │
│ sans internet   │ avoir une preuve │ standardisé               │
└─────────────────┴──────────────────┴───────────────────────────┘
```

---

## 2. Diagramme d'architecture global

```
╔══════════════════════════════════════════════════════════════════╗
║                         CLIENTS                                  ║
║  ┌────────────────┐  ┌──────────────┐  ┌───────────────────┐    ║
║  │  Web Dashboard │  │ Mobile (RN)  │  │ WhatsApp (notify) │    ║
║  │  (Next.js)     │  │  [future]    │  │    (token only)   │    ║
║  └────────┬───────┘  └──────┬───────┘  └─────────┬─────────┘    ║
╚═══════════╪═════════════════╪═════════════════════╪═════════════╝
            │                 │                     │
╔═══════════▼═════════════════▼═════════════════════▼═════════════╗
║                    API GATEWAY (service: gateway)                ║
║           Auth (JWT/OAuth2) | RBAC | Audit Log | Rate Limit      ║
╚══════════════════════════════════════════════════════════════════╝
                    │
       ┌────────────▼────────────────────────────────────┐
       │              REDIS STREAMS (Event Bus)           │
       │   topics: ingestion.* | preprocess.* | ...       │
       └─────────┬──────────┬───────────┬───────┬────────┘
                 │          │           │       │
    ┌────────────▼──┐  ┌────▼─────┐  ┌─▼───┐  ┌▼──────────┐
    │  CORE SERVICES│  │ AI/ML    │  │SRCH │  │INTEGRATION│
    │               │  │ SERVICES │  │     │  │           │
    │ ● patient     │  │          │  │●srch│  │●connector │
    │ ● ingestion   │  │●inference│  │     │  │  SDK      │
    │ ● preprocess  │  │●evidence │  │     │  │●DMI sync  │
    │ ● imaging     │  │●predict  │  │     │  │           │
    └───────┬───────┘  └────┬─────┘  └──┬──┘  └─────┬─────┘
            │               │            │           │
╔═══════════▼═══════════════▼════════════▼═══════════▼═══════════╗
║                       DATA LAYER                                 ║
║  ┌──────────┐ ┌──────┐ ┌────────┐ ┌────────────┐ ┌──────────┐  ║
║  │PostgreSQL│ │Redis │ │ MinIO  │ │Meilisearch │ │ Orthanc  │  ║
║  │(relations│ │(cache│ │(blobs) │ │  (search)  │ │ (DICOM)  │  ║
║  │ + jobs)  │ │+queue│ │        │ │            │ │          │  ║
║  └──────────┘ └──────┘ └────────┘ └────────────┘ └──────────┘  ║
╚═════════════════════════════════════════════════════════════════╝
```

---

## 3. Architecture Offline (Edge) vs Hub

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODE EDGE (offline)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              EDGE RUNTIME (Docker ou bare)               │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │  Mini-DMI    │  │   OCR +      │  │  Knowledge   │   │   │
│  │  │  (patient +  │  │   Preprocess │  │  Pack        │   │   │
│  │  │   encounter) │  │              │  │  (indexé)    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ MedGemma     │  │  Job Queue   │  │  Local       │   │   │
│  │  │ ONNX (quant) │  │  (SQLite)    │  │  Notifs      │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                    STORE & FORWARD                               │
│                    (quand internet)                              │
│                           │                                      │
└───────────────────────────▼─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    MODE HUB (cloud/serveur)                     │
│                                                                  │
│  Pillar-0 GPU | MedGemma complet | Prédictions lourdes          │
│  Knowledge Pack updates | Analytics | Agrégation multi-sites    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Pipeline agent (event-driven)

```
                        DOCUMENT/DICOM reçu
                               │
                    ┌──────────▼──────────┐
                    │   IngestionAgent    │
                    │  (upload/connector) │
                    └──────────┬──────────┘
                               │ ingestion.received
               ┌───────────────▼───────────────┐
               │                               │
    ┌──────────▼──────────┐      ┌─────────────▼───────────┐
    │   PreprocessAgent   │      │   ImagingImportAgent    │
    │ OCR+clean+extract   │      │   (DICOM → Orthanc)     │
    └──────────┬──────────┘      └─────────────┬───────────┘
               │ preprocess.completed           │ imaging.imported
               └───────────┬───────────────────┘
                           │
               ┌───────────▼──────────────┐
               │      MedGemmaAgent       │◄── pillar0.completed
               │  synthèse + claims       │
               └───────────┬──────────────┘
                           │          │
                    ┌──────▼───┐  ┌───▼──────────┐
                    │Pillar0   │  │PredictionAgent│
                    │Agent     │  │(si timeline)  │
                    └──────────┘  └───┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  EvidenceGuardAgent  │
                           │  (valide tous claims)│
                           └──┬──────────────┬───┘
                              │              │
                    evidence.  │    evidence. │
                    validate   │    blocked   │
                    .completed │              │
                              │              │
               ┌──────────────▼──┐    ┌──────▼──────────┐
               │  IndexerAgent   │    │  Repair route   │
               │ (patient+knowl) │    │  (MedGemma)     │
               └──────────┬──────┘    └─────────────────┘
                          │ index.update.completed
                          │
               ┌──────────▼──────────┐
               │  NotificationAgent  │
               │  (dashboard+WA)     │
               └─────────────────────┘
```

---

## 5. Services détaillés

### 5.1 Gateway Service (`services/gateway/`)
**Rôle** : Point d'entrée unique, auth, RBAC, audit
- JWT validation + refresh tokens
- RBAC : roles `admin | doctor | nurse | viewer | system`
- Audit log : toute action traçable (qui, quand, quoi, IP)
- Rate limiting par IP + par token
- Reverse proxy vers services internes

### 5.2 Patient Service (`services/patient/`)
**Rôle** : Mini-DMI — dossiers patients + encounters
- CRUD patient avec `external_ids[]` (mapping DMI)
- Encounters (consultations, hospitalisations)
- Timeline reconstruction (même si données fragmentées)
- Fonctionne 100% offline (SQLite en edge)

### 5.3 Ingestion Service (`services/ingestion/`)
**Rôle** : Recevoir tout type de document
- Upload PDF, photo (JPEG/PNG/TIFF), DICOM
- Import via connecteurs (API, CSV, DB)
- Validation mime-type + taille
- Stockage brut dans MinIO
- Publication `ingestion.received`

### 5.4 Preprocess Service (`services/preprocess/`)
**Rôle** : Nettoyer, OCR, extraire données structurées
- Nettoyage visuel (deskew, denoising, contrast)
- OCR multilingue (EasyOCR + Tesseract fallback)
- Extraction : labs, constantes, dates, diagnostics
- Quality scoring (0–1, flag `rescan_needed`)
- Block extraction avec coordonnées (bbox pour EvidenceRef)

### 5.5 Imaging Service (`services/imaging/`)
**Rôle** : Gestion DICOM
- Proxy Orthanc (DICOM server)
- Endpoints viewer (series, instances, thumbnails)
- Gestion séries/instances/études
- Export overlays (ROI depuis Pillar-0)

### 5.6 Inference Service (`services/inference/`)
**Rôle** : Runners IA (Pillar-0 + MedGemma)
- `Pillar0Runner` : analyse CT/MRI 3D → findings + overlays
- `MedGemmaRunner` : synthèse clinique + claims
- Routing automatique : edge (ONNX quantisé) ou hub (complet)
- Job tracking avec retries

### 5.7 Evidence Service (`services/evidence/`)
**Rôle** : EvidenceGuard + stockage preuves
- Policy engine : valide/bloque tout claim
- Storage EvidenceRef (PDF bbox, DICOM slice, lab, knowledge)
- Renderer : highlights PDF, overlays DICOM
- API pour récupérer preuves cliquables

### 5.8 Prediction Service (`services/prediction/`)
**Rôle** : Prédictions longitudinales
- Architecture plugin (chaque modèle = plugin)
- Fenêtres standard : 30d, 6m, 1y, 2y
- Input : FeatureTimeline (labs trend, findings, traitements)
- Output : Prediction + claims sourcés

### 5.9 Search Service (`services/search/`)
**Rôle** : Recherche patient + documentaire
- Index patient (timeline, labs, diagnostics)
- Index Knowledge Pack (guidelines, protocoles)
- Q/A offline via Meilisearch + MedGemma
- Séparation claire : connaissance générale vs contexte patient

### 5.10 Integration Service (`services/integration/`)
**Rôle** : Connector SDK + sync DMI
- Interfaces standardisées (`pullPatients`, `pushReport`, etc.)
- Modes : shadow | link | write-back
- Mapping IDs DMI ↔ RYX
- Connecteurs built-in : HL7 FHIR, CSV, OpenMRS

### 5.11 Notification Service (`services/notification/`)
**Rôle** : Alertes sans PHI
- Dashboard feed (WebSocket)
- WhatsApp Business API (token-only, no PHI)
- Format médical court (SOAP / Impression/Evidence/Next)
- Règles de déduplication et throttling

### 5.12 Observability Service (`services/observability/`)
**Rôle** : Métriques, logs, tracing, incidents
- Prometheus metrics (toutes latences, queues, errors)
- OpenTelemetry traces (distribué)
- Structured logging (JSON, pas de PHI)
- OpsAgent : alertes infra (GPU down, disk full, queue stuck)

---

## 6. Déploiements

### 6.1 Développement local
```bash
docker-compose -f docker-compose.infra.yml up -d
make dev
```

### 6.2 Edge (offline)
```bash
docker-compose -f docker-compose.edge.yml up -d
```
Services edge : gateway, patient, ingestion, preprocess, search, notification + SQLite + Meilisearch locale

### 6.3 Hub (production)
```bash
helm install ryx ./infra/helm/ryx -f values.production.yaml
```
Kubernetes multi-services, PostgreSQL HA, Redis Cluster, MinIO distributed

---

## 7. Sécurité

- **Auth** : JWT (access 15min + refresh 7j) + OAuth2 flows
- **RBAC** : granulaire par service/action
- **Audit** : toute lecture/écriture patient loguée
- **PHI** : jamais dans logs, jamais dans notifications externes
- **Chiffrement** : TLS in-transit, AES-256 at-rest (MinIO + Postgres)
- **Isolation** : services en réseau Docker isolé, pas d'exposition directe DB

---

## 8. Knowledge Pack

Structure :
```
knowledge-pack/
├── manifest.json          # version, date, sources
├── guidelines/            # WHO, Ministère Santé RDC, etc.
├── protocols/             # protocoles cliniques
├── references/            # références médicales
└── index/                 # index Meilisearch sérialisé
```

Mise à jour :
- Via sync réseau (hub → edge) quand connectivité
- Via "update pack" USB/SD (versioning obligatoire)
- Format : archive signée avec manifest de version

---

## 9. Modèles IA intégrés

| Modèle | Rôle | Mode |
|--------|------|------|
| **Pillar-0** | Vision 3D CT/MRI → findings + overlays | Hub (GPU) + Edge si GPU dispo |
| **MedGemma 1.5** | Raisonnement clinique → synthèse, claims | Hub (complet) + Edge (ONNX quantisé) |
| **Plugins Prediction** | Scores longitudinaux 30d/6m/1y/2y | Hub (lourd) + Edge (léger) |
| **EasyOCR** | OCR multilingue (FR/EN/local) | Edge + Hub |

---

## 10. Chemins d'évolution

1. **V1** (MVP) : Mini-DMI + OCR + MedGemma hub + EvidenceGuard + Dashboard
2. **V2** : Pillar-0 intégré + Prédictions + Knowledge Pack offline
3. **V3** : App mobile + Connector SDK multi-DMI + Edge GPU
4. **V4** : Multi-site analytics + apprentissage fédéré (sans PHI)

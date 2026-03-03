# RYX — Contrats API

> Contract-first. Ces specs définissent les interfaces avant l'implémentation.
> Format : OpenAPI 3.1 (résumé structuré)

---

## Base URL

- **Hub** : `https://api.ryx.health/v1`
- **Edge** : `http://localhost:8000/v1`

---

## Authentification

```
Authorization: Bearer <jwt_access_token>
```

Tous les endpoints requièrent auth sauf `/auth/token` et `/health`.

---

## Endpoints par domaine

### Auth (`/auth`)
```
POST   /auth/token          # Login → access_token + refresh_token
POST   /auth/refresh        # Refresh access_token
POST   /auth/logout         # Invalide le refresh_token
GET    /auth/me             # Profil utilisateur courant
```

### Patients (`/patients`)
```
POST   /patients                        # Créer patient
GET    /patients                        # Liste patients (paginée)
GET    /patients/:patient_id            # Détail patient
PATCH  /patients/:patient_id            # Mettre à jour patient
GET    /patients/:patient_id/timeline   # Timeline complète (encounters + docs + labs)
GET    /patients/:patient_id/summary    # Résumé IA du dossier
POST   /patients/search                 # Recherche par nom/id/phone
```

### Encounters (`/encounters`)
```
POST   /encounters                          # Créer encounter
GET    /encounters/:encounter_id            # Détail encounter
PATCH  /encounters/:encounter_id            # Mettre à jour
GET    /encounters/:encounter_id/documents  # Documents liés
GET    /encounters/:encounter_id/labs       # Labs liés
POST   /encounters/:encounter_id/labs       # Ajouter lab manuellement
GET    /encounters/:encounter_id/report     # Rapport IA de l'encounter
```

### Documents (`/documents`)
```
POST   /documents/upload                   # Upload document (multipart)
GET    /documents/:doc_id                  # Metadata du document
DELETE /documents/:doc_id                  # Supprimer (soft delete)
GET    /documents/:doc_id/status           # Statut preprocessing
```

### Viewer (`/viewer`)
```
GET    /viewer/doc/:doc_id                 # PDF viewer avec highlights
GET    /viewer/doc/:doc_id/page/:page      # Page spécifique + bbox overlays
GET    /viewer/dicom/:study_id             # DICOM viewer (OHIF proxy)
GET    /viewer/dicom/:study_id/series      # Liste séries
GET    /viewer/dicom/:study_id/thumbnail   # Thumbnail study
```

### Imaging (`/imaging`)
```
POST   /imaging/import                     # Import DICOM (file ou URL)
GET    /imaging/studies/:study_id          # Metadata étude
GET    /imaging/studies/:study_id/series   # Séries
POST   /imaging/studies/:study_id/analyze  # Trigger analyse Pillar-0
GET    /imaging/studies/:study_id/findings # Findings Pillar-0
```

### Reports (`/reports`)
```
GET    /reports/:encounter_id/latest       # Dernier rapport d'un encounter
GET    /reports/:report_id                 # Rapport par ID
POST   /reports/:encounter_id/generate     # Générer rapport (trigger MedGemma)
GET    /reports/:report_id/claims          # Claims d'un rapport
PATCH  /reports/:report_id/claims/:claim_id # Valider/rejeter un claim (clinicien)
```

### Prédictions (`/predictions`)
```
GET    /predictions/:patient_id            # Dernières prédictions
GET    /predictions/:patient_id?window=30d # Prédiction fenêtre spécifique
POST   /predictions/:patient_id/compute   # Déclencher calcul prédictions
GET    /predictions/:prediction_id/factors # Top facteurs
```

### Recherche documentaire (`/docsearch`)
```
POST   /docsearch/query                    # Q/A sur Knowledge Pack
GET    /docsearch/topics                   # Liste des topics disponibles
GET    /docsearch/status                   # Status du Knowledge Pack (version, date)
```

### Intégration (`/integration`)
```
GET    /integration/connectors             # Liste connecteurs disponibles
POST   /integration/connectors/:id/sync   # Déclencher sync
GET    /integration/connectors/:id/status # Statut du connecteur
POST   /integration/connectors/:id/test   # Tester la connexion
GET    /integration/sync/history          # Historique des syncs
```

### Notifications (`/notifications`)
```
GET    /notifications/feed                 # Feed temps réel (WebSocket upgrade)
GET    /notifications                      # Liste notifications
PATCH  /notifications/:id/read            # Marquer comme lu
GET    /notifications/preferences         # Préférences utilisateur
PATCH  /notifications/preferences         # Mettre à jour préférences
```

### Admin (`/admin`)
```
GET    /admin/jobs                         # File de jobs (status, retry)
POST   /admin/jobs/:job_id/retry          # Retry manuel
GET    /admin/jobs/:job_id/logs           # Logs d'un job
GET    /admin/health                      # Health check détaillé
GET    /admin/metrics                     # Métriques (Prometheus format)
GET    /admin/knowledge-pack/version      # Version Knowledge Pack installée
POST   /admin/knowledge-pack/update      # Déclencher mise à jour
```

---

## Schémas de requête/réponse (exemples)

### POST /documents/upload
```json
// Request: multipart/form-data
{
  "file": "<binary>",
  "encounter_id": "uuid",
  "patient_id": "uuid",
  "document_type": "lab_report | imaging | clinical_note | prescription | other",
  "document_date": "2026-01-15T00:00:00Z"  // optionnel
}

// Response 201
{
  "doc_id": "uuid",
  "status": "queued",
  "job_id": "uuid",
  "message": "Document reçu, preprocessing en cours"
}
```

### POST /docsearch/query
```json
// Request
{
  "query": "prise en charge paludisme grave adulte",
  "context_type": "knowledge | patient | both",
  "patient_id": "uuid",  // optionnel, si context_type inclut patient
  "top_k": 5,
  "language": "fr"
}

// Response 200
{
  "query": "prise en charge paludisme grave adulte",
  "answer": "Selon les directives OMS 2023, le traitement de première ligne...",
  "sources": [
    {
      "kind": "knowledge",
      "knowledge_doc_id": "uuid",
      "chunk_id": "chunk-42",
      "excerpt": "Artémisinine IV recommandée en cas de...",
      "confidence": 0.94,
      "title": "WHO Malaria Treatment Guidelines 2023",
      "source": "WHO"
    }
  ],
  "context_type_used": "knowledge",
  "offline": true,
  "knowledge_pack_version": "2024-Q4"
}
```

### GET /predictions/:patient_id?window=30d
```json
// Response 200
{
  "patient_id": "uuid",
  "window": "30d",
  "predictions": [
    {
      "prediction_id": "uuid",
      "model": "renal-deterioration-v2",
      "score": 0.73,
      "band": "high",
      "computed_at": "2026-03-03T10:00:00Z",
      "top_factors": [
        {
          "feature": "creatinine_trend_30d",
          "contribution": 0.42,
          "direction": "positive"
        }
      ],
      "claims": [
        {
          "claim_id": "uuid",
          "type": "alert",
          "text": "Risque élevé de détérioration rénale dans 30 jours",
          "criticality": "high",
          "status": "valid",
          "evidence_refs": [
            {
              "kind": "lab",
              "lab_id": "uuid",
              "test": "créatinine",
              "value": 2.4,
              "unit": "mg/dL",
              "date": "2026-02-28T00:00:00Z",
              "confidence": 0.98
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Codes d'erreur standardisés

```json
// Format erreur standard
{
  "error": {
    "code": "EVIDENCE_BLOCKED",
    "message": "Claim rejeté : aucune preuve suffisante trouvée",
    "detail": {
      "claim_id": "uuid",
      "type": "alert",
      "blocked_reason": "evidence_refs.length == 0"
    }
  },
  "request_id": "uuid"
}
```

| Code | HTTP | Description |
|------|------|-------------|
| `AUTH_REQUIRED` | 401 | Token manquant ou invalide |
| `FORBIDDEN` | 403 | Rôle insuffisant |
| `NOT_FOUND` | 404 | Resource introuvable |
| `VALIDATION_ERROR` | 422 | Données invalides (Pydantic) |
| `EVIDENCE_BLOCKED` | 422 | Claim sans preuve |
| `JOB_QUEUED` | 202 | Traitement asynchrone |
| `OFFLINE_MODE` | 503 | Service hub non disponible en mode edge |
| `INTERNAL_ERROR` | 500 | Erreur interne (loguée, ref dans réponse) |

---

## Pagination standard

```json
// Tous les endpoints liste utilisent
// Query params: ?page=1&per_page=20&sort=created_at&order=desc
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

## WebSocket (notifications temps réel)

```
WS /notifications/feed?token=<jwt>

// Message format
{
  "type": "alert | report_ready | job_completed | ops_incident",
  "payload": {
    "patient_id": "uuid",
    "encounter_id": "uuid",
    "message": "Rapport prêt pour Dr. Mukendi",
    "criticality": "high",
    "created_at": "2026-03-03T10:00:00Z"
  }
}
```

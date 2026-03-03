# RYX — Agent Plane (Design)

> 11 agents 24/7, event-driven, idempotents, offline-ready.

---

## Pattern commun de tous les agents

```python
# packages/shared/ryx_shared/agent_base.py

class BaseAgent:
    """
    Pattern commun :
    - Consumer group Redis Streams
    - Idempotence via job_id
    - Retry avec backoff exponentiel
    - Structured logging (pas de PHI)
    - Metrics Prometheus
    """

    name: str  # "ingestion-agent"
    input_topic: str  # "ingestion.received"
    consumer_group: str  # "ingestion-agent-group"

    async def run(self):
        await self._ensure_consumer_group()
        while True:
            messages = await self.redis.xreadgroup(
                groupname=self.consumer_group,
                consumername=self.instance_id,
                streams={self.input_topic: ">"},
                count=10,
                block=5000  # ms
            )
            for stream, msgs in (messages or []):
                for msg_id, data in msgs:
                    await self._handle_with_retry(msg_id, data)

    async def _handle_with_retry(self, msg_id: str, data: dict):
        job_id = data.get("job_id")
        # Idempotence : vérifier si déjà traité
        if await self._is_processed(job_id):
            await self.redis.xack(self.input_topic, self.consumer_group, msg_id)
            return

        for attempt in range(self.max_retries):
            try:
                await self.process(data)
                await self.redis.xack(self.input_topic, self.consumer_group, msg_id)
                await self._mark_done(job_id)
                return
            except Exception as e:
                if attempt == self.max_retries - 1:
                    await self._mark_failed(job_id, str(e))
                    await self._publish_incident(e)
                else:
                    await asyncio.sleep(2 ** attempt)  # backoff

    async def process(self, data: dict):
        """À implémenter par chaque agent"""
        raise NotImplementedError
```

---

## 1. IngestionAgent

**Service** : `services/ingestion`
**Input** : uploads directs + pulls connecteurs
**Output topic** : `ingestion.received`

```
Responsabilités :
- Recevoir fichiers (PDF, image, DICOM)
- Valider (mime-type, taille, intégrité)
- Stocker dans MinIO (/raw/{patient_id}/{doc_id})
- Créer Document en DB (status: received)
- Publier ingestion.received

Polling connecteurs (schedule) :
- Connecteur FHIR/DMI → pullPatients(since=last_sync)
- Convertir en Document + stocker
```

---

## 2. PreprocessAgent

**Service** : `services/preprocess`
**Input topic** : `ingestion.received`
**Output topic** : `preprocess.completed`

```
Responsabilités :
- Nettoyage visuel : deskew, denoising, contrast enhancement
- OCR : EasyOCR (multilingue) + Tesseract (fallback)
- Extraction structurée :
  - Labs (test, valeur, unité, date, ref_range)
  - Constantes vitales
  - Dates de documents
  - Diagnostics mentionnés
- Quality scoring (0-1, flag rescan_needed < 0.3)
- Stocker blocs OCR avec bbox (pour EvidenceRef)
- Sauvegarder résultats en DB
- Publier preprocess.completed

Mode edge : tourne identique mais avec modèles locaux
```

---

## 3. ImagingImportAgent

**Service** : `services/imaging`
**Input** : DICOM upload direct ou via ingestion
**Output topic** : `imaging.imported`

```
Responsabilités :
- Importer DICOM dans Orthanc (API REST)
- Extraire metadata (modality, body_part, date, series)
- Créer ImagingStudy en DB avec orthanc_study_id
- Générer thumbnail
- Publier imaging.imported
```

---

## 4. Pillar0Agent

**Service** : `services/inference`
**Input topics** : `imaging.imported`, `pillar0.requested`
**Output topic** : `pillar0.completed`

```
Responsabilités :
- Routing (edge GPU ou hub GPU via store&forward)
- Télécharger séries DICOM depuis Orthanc
- Exécuter Pillar-0 (modèle vision 3D)
- Extraire findings (label, severity, localisation)
- Générer overlays (ROI sur slices)
- Créer EvidenceRef(kind=dicom) pour chaque finding
- Stocker overlays dans MinIO
- Publier pillar0.completed

Routing logic :
- Si RYX_MODE=edge ET GPU local disponible → run local
- Sinon → sérialiser job → file hub → attendre résultats
```

---

## 5. MedGemmaAgent

**Service** : `services/inference`
**Input topics** : `preprocess.completed` (+ optionnel `pillar0.completed`)
**Output topic** : `medgemma.completed`

```
Responsabilités :
- Assembler contexte (docs OCR + findings imaging + labs + historique)
- Prompt engineering (format médical structuré)
- Exécuter MedGemma 1.5 :
  - Synthèse clinique
  - Recommandations
  - Questions à poser au patient
  - Alertes (hypoxie, dégradation rénale, etc.)
- Chaque sortie → Claim(status=pending) avec evidence_refs tentatives
- Publier medgemma.completed (claims pending)

Routing logic :
- Hub mode → MedGemma 1.5 complet (full precision)
- Edge mode → MedGemma ONNX quantisé (int8/int4)

Contraintes prompt :
- Séparer clairement "contexte patient" vs "connaissance générale"
- Chaque claim doit citer sa source dans le prompt
- Format de sortie structuré (JSON schema enforced)
```

---

## 6. PredictionAgent

**Service** : `services/prediction`
**Input topic** : `medgemma.completed` + timeline features
**Output topic** : `prediction.completed`

```
Responsabilités :
- Extraire FeatureTimeline(patient_id, window) :
  - labs trend (slope + dernière valeur)
  - findings imagerie (sévérité, date)
  - diagnostics actifs
  - traitements + réponses
- Exécuter plugins prédiction par fenêtre (30d, 6m, 1y, 2y)
- Chaque plugin → Prediction + Claims sourcés
- Publier prediction.completed

Architecture plugin :
class PredictionPlugin:
    name: str
    windows: list[PredictionWindow]
    async def predict(self, timeline: FeatureTimeline) -> Prediction: ...
```

---

## 7. EvidenceGuardAgent

**Service** : `services/evidence`
**Input topics** : `medgemma.completed`, `prediction.completed`
**Output topics** : `evidence.validate.completed`, `evidence.blocked`

```
Responsabilités :
- Récupérer tous les Claims pending
- Appliquer EvidenceGuard policy sur chaque claim
- Claims valides → status=valid → evidence.validate.completed
- Claims bloqués → status=blocked → evidence.blocked

Route repair (optionnel) :
- Pour claims bloqués à criticality=high :
  - Republier vers MedGemma avec prompt "find evidence for: {claim}"
  - Si toujours pas de preuve → needs_human

SLA : < 1s par claim (policy engine in-memory)
```

---

## 8. IndexerAgent

**Service** : `services/search`
**Input topic** : `evidence.validate.completed`
**Output topic** : `index.update.completed`

```
Responsabilités :
- Mettre à jour index patient Meilisearch :
  - Timeline (encounters, docs, labs)
  - Findings validés
  - Claims validés
- Mettre à jour index Knowledge Pack (si nouveau contenu)
- Publier index.update.completed

Offline : Meilisearch tourne en local → index mis à jour sans internet
```

---

## 9. IntegrationSyncAgent

**Service** : `services/integration`
**Input** : schedule + `integration.sync.requested`
**Output topic** : `integration.sync.completed`

```
Responsabilités :
- Pour chaque connecteur configuré :
  - pullPatients(since=last_sync)
  - pullEncounters(since=last_sync)
  - pullDocuments(since=last_sync)
  - Mapper external_ids ↔ RYX patient_id
- Write-back (si mode activé) :
  - pushReport(encounter_id, report_ref)
  - pushAlert(patient_id, alert_ref)
- Publier integration.sync.completed

Shadow mode : lecture seule, aucune écriture vers DMI
```

---

## 10. NotificationAgent

**Service** : `services/notification`
**Input topics** : `evidence.validate.completed`, `ops.incident`
**Output topic** : `notify.sent`

```
Responsabilités :
- Pour chaque alerte validée (criticality >= moderate) :
  - Dashboard : push WebSocket temps réel
  - WhatsApp (si configuré) :
    - Construire message SANS PHI
    - Format : "🔔 RYX | Patient #{token} | {impression_courte}"
    - Lien sécurisé vers dashboard (token expirant 24h)
- Déduplication (pas de doublon si même alerte < 1h)
- Throttling par patient (max 3 alertes/heure)

Format WhatsApp (JAMAIS de PHI) :
"🔔 *RYX Alert* | Dossier #RYX-{5chars} | {impression}
→ Voir détails : {secure_link}
_Expiry: 24h_"
```

---

## 11. OpsAgent

**Service** : `services/observability`
**Input** : métriques + backlogs
**Output topic** : `ops.incident`

```
Responsabilités :
- Surveiller :
  - GPU utilisation + erreurs Pillar-0/MedGemma
  - Queue Redis (backlog > seuil)
  - Disk space (MinIO, Orthanc)
  - Sync failures (IntegrationSync)
  - Service health (heartbeats)
- Créer incident si seuil dépassé
- Publier ops.incident → NotificationAgent (admin)

Métriques exposées (Prometheus) :
- ryx_jobs_queued{type="..."}
- ryx_agent_latency_seconds{agent="..."}
- ryx_claims_blocked_total
- ryx_evidence_guard_validations_total
- ryx_disk_usage_bytes{service="..."}
```

---

## Corrélation des pipelines

Chaque pipeline est tracé via `correlation_id` (UUID unique par encounter):
```
ingestion.received (correlation_id=X)
  → preprocess.completed (correlation_id=X)
  → medgemma.completed (correlation_id=X)
  → evidence.validate.completed (correlation_id=X)
  → notify.sent (correlation_id=X)
```

Permet de retrouver tout le pipeline dans les logs et traces OpenTelemetry.

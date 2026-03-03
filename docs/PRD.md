# TECH PRD v3.2 — RYX (Clinical AI Layer)

> Document original archivé ici pour référence.
> Pour l'architecture technique détaillée, voir `docs/ARCHITECTURE.md`.

---

Ce fichier contient le PRD original fourni par l'équipe produit.

## Résumé exécutif

RYX est une couche IA clinique conçue pour les hôpitaux, principalement en contexte ressources limitées (RDC).

**Trois principes non-négociables :**
1. **Offline-first** : fonctions essentielles sans internet
2. **Evidence-first** : toute assertion sourcée (EvidenceGuard)
3. **Interop-first** : Connector SDK DMI standardisé

**Modèles IA imposés :**
- **Pillar-0** : vision 3D CT/MRI
- **MedGemma 1.5** : raisonnement clinique
- **Plugins prédiction** : scores longitudinaux 30d/6m/1y/2y

**Stack choisie :**
- Backend : Python 3.12 + FastAPI (12 microservices)
- Frontend : TypeScript + Next.js 14
- BD : PostgreSQL + Redis + MinIO + Meilisearch + Orthanc
- Event Bus : Redis Streams
- Edge : ONNX Runtime + SQLite + Meilisearch local

Voir `docs/ARCHITECTURE.md` pour les détails complets.
Voir `docs/stack.md` pour les justifications de stack.
Voir `docs/adr/` pour les Architecture Decision Records.

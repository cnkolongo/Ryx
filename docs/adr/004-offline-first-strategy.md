# ADR-004 — Stratégie Offline-First (Edge vs Hub)

**Date** : 2026-03-03
**Statut** : Accepté

## Contexte
En RDC, beaucoup d'hôpitaux n'ont pas d'internet stable. RYX doit fonctionner complètement offline pour les fonctions essentielles, et synchroniser quand la connectivité est disponible.

## Décision
Architecture à deux tiers : **Edge** (offline) + **Hub** (cloud/serveur central).

### Ce qui tourne obligatoirement en Edge
| Fonction | Technologie |
|----------|-------------|
| Mini-DMI (CRUD patient/encounter) | FastAPI + SQLite |
| OCR + Preprocessing | EasyOCR + Tesseract |
| Index patient (recherche) | Meilisearch (local) |
| Knowledge Pack Q/A | MedGemma ONNX quantisé + Meilisearch |
| Notifications locales | Redis local (ou SQLite fallback) |
| Queue jobs hub | SQLite (jobs sérialisés) |

### Ce qui peut être différé (Hub)
| Fonction | Raison |
|----------|--------|
| Pillar-0 (gros CT/MRI) | GPU intensif |
| MedGemma complet | Modèle full trop lourd |
| Prédictions lourdes | Compute intensif |
| Knowledge Pack updates | Réseau requis |
| Analytics multi-sites | Hub uniquement |

### Store & Forward
```python
# Pattern pour jobs hub différés
class DeferredJob(BaseModel):
    job_id: UUID
    type: JobType
    payload: dict
    created_at: datetime
    # Stocké dans SQLite edge → envoyé au Hub quand connectivité
```

### Knowledge Pack distribution
- **En ligne** : sync automatique via réseau (hub → edge)
- **Hors ligne** : "update pack" signé (USB/SD card) avec manifest de version
- **Format** : archive `.kpack` (tar.gz signé) avec `manifest.json`

## Détection de mode
```python
# config.py
class RyxMode(str, Enum):
    HUB = "hub"
    EDGE = "edge"
    HYBRID = "hybrid"  # edge avec connectivité intermittente

RYX_MODE = os.getenv("RYX_MODE", "hub")
```

## Conséquences
- `+` Fonctionnement complet sans internet (fonctions essentielles)
- `+` Sync transparente quand connectivité disponible
- `+` Résilience aux pannes réseau
- `-` Complexité de synchronisation bidirectionnelle
- `-` Deux sets de config (edge + hub)
- Mitigation : Docker Compose séparé par mode, feature flags par mode

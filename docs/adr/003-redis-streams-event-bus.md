# ADR-003 — Redis Streams comme Event Bus (MVP)

**Date** : 2026-03-03
**Statut** : Accepté

## Contexte
RYX est event-driven. 11 agents consomment et publient des events. On a besoin d'un event bus qui :
- Fonctionne aussi en mode edge (offline)
- Soit simple à déployer
- Supporte consumer groups (parallélisme + retry)
- Soit idempotent

## Décision
**Redis Streams** pour le MVP. Pas de Kafka, pas de RabbitMQ.

## Raisons
1. **Déjà présent** : Redis est utilisé pour le cache et les sessions → pas de service supplémentaire
2. **Consumer Groups** : natif dans Redis Streams (xreadgroup, xack)
3. **Offline-compatible** : une instance Redis tourne en edge
4. **Persistance** : Redis AOF/RDB pour ne pas perdre les events
5. **Simplicité** : pas de ZooKeeper, pas de broker cluster pour MVP

## Chemin de migration (scale)
Quand le volume le justifie :
- **NATS JetStream** : léger, cloud-native, bon pour edge/hub
- **Apache Kafka** : si volume > 100k events/jour et analytics needed

## Format event (standard)
```python
{
  "event_id": "uuid",
  "topic": "ingestion.received",
  "version": "1.0",
  "timestamp": "2026-03-03T10:00:00Z",
  "payload": {...},
  "source_service": "ingestion",
  "correlation_id": "uuid"  # pour tracer un pipeline
}
```

## Conséquences
- `+` Déploiement simplifié (un seul Redis)
- `+` Latence faible (in-memory)
- `+` Consumer groups avec retry intégré
- `-` Redis Streams moins robuste que Kafka pour très gros volumes
- `-` Pas de schema registry natif (on utilise Pydantic pour validation)
- Mitigation : consumer groups + ACK + retry dans chaque agent

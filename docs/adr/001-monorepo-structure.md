# ADR-001 — Structure Monorepo

**Date** : 2026-03-03
**Statut** : Accepté

## Contexte
RYX comprend 12 services backend, 1 app frontend, des packages partagés et une infrastructure complexe. On doit organiser le code de manière à faciliter le vibecoding tout en gardant les services indépendants en déploiement.

## Décision
Monorepo avec structure manuelle (sans Nx/Turborepo pour réduire la complexité initiale).

```
/services/   # Python FastAPI services
/apps/       # Next.js frontend
/packages/   # Python packages partagés
/infra/      # Docker/K8s
/docs/       # Documentation
```

## Alternatives considérées
- **Polyrepo** : trop de friction pour vibecoding (12 repos à gérer)
- **Nx monorepo** : overhead de configuration trop élevé pour démarrer
- **Lerna** : focalisé Node, ne couvre pas Python

## Conséquences
- `+` Changements cross-services en un seul commit
- `+` Packages partagés faciles à synchroniser
- `-` `git clone` plus lourd avec le temps
- Mitigation : `.gitignore` modèles ML + DICOM data

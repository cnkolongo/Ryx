# ADR-005 — EvidenceGuard : Policy Engine Central

**Date** : 2026-03-03
**Statut** : Accepté

## Contexte
RYX fait des recommandations médicales. Une recommandation non prouvée peut être dangereuse. On a besoin d'un mécanisme qui garantit que toute sortie "utile" est sourcée.

## Décision
**EvidenceGuard** : policy engine partagé (package Python), intégré à chaque agent et service qui produit des Claims.

### Règles immuables
```python
class EvidenceGuardPolicy:
    """
    Règles :
    1. Tout claim DOIT avoir evidence_refs.length >= 1
    2. Si claim touche patient → au moins un EvidenceRef.kind in (doc, dicom, lab)
    3. Si claim est purement documentaire → EvidenceRef.kind == knowledge
    4. Pas de mélange guideline + patient sans séparateur explicite
    """

    def validate(self, claim: Claim) -> ClaimValidationResult:
        errors = []

        if len(claim.evidence_refs) == 0:
            errors.append("NO_EVIDENCE: claim has no evidence_refs")

        if self._is_patient_claim(claim):
            patient_refs = [r for r in claim.evidence_refs
                           if r.kind in ("doc", "dicom", "lab")]
            if not patient_refs:
                errors.append("PATIENT_CLAIM_NO_PATIENT_EVIDENCE")

        if errors:
            return ClaimValidationResult(
                valid=False,
                claim_id=claim.claim_id,
                errors=errors,
                action=ValidationAction.BLOCK
            )

        return ClaimValidationResult(valid=True, claim_id=claim.claim_id)
```

### Ce que EvidenceGuard ne peut PAS faire
- Vérifier la **qualité** de la preuve (confidence > seuil)
- Vérifier la **pertinence** médicale (rôle de MedGemma)
- Remplacer le jugement clinique

### Intégration
```python
# Dans chaque agent qui produit des Claims :
guard = EvidenceGuard()
results = await guard.validate_batch(claims)

for result in results:
    if not result.valid:
        claim.status = ClaimStatus.BLOCKED
        await event_bus.publish("evidence.blocked", {
            "claim_id": str(result.claim_id),
            "reason": result.errors
        })
    else:
        claim.status = ClaimStatus.VALID
```

### Route "repair"
Quand un claim est bloqué, l'EvidenceGuardAgent peut router vers MedGemma pour tenter de trouver des preuves additionnelles dans le dossier.

## Conséquences
- `+` Sécurité médicale garantie par design
- `+` Traçabilité : toute décision a une preuve cliquable
- `+` "Better empty than wrong" : si pas de preuve → rien n'est affiché
- `-` Peut créer des faux positifs (claims bloqués alors que preuves existent mais mal extraites)
- Mitigation : route repair + escalade `needs_human` + feedback clinicien

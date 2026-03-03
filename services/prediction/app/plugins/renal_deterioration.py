"""Plugin exemple : prédiction de détérioration rénale."""

from abc import ABC, abstractmethod
from uuid import uuid4

from ryx_shared.claims import Claim, ClaimType, CriticalityLevel
from ryx_shared.models import Prediction, PredictionWindow, RiskBand, PredictionFactor


class BasePredictionPlugin(ABC):
    name: str
    supported_windows: list[PredictionWindow] = list(PredictionWindow)

    @abstractmethod
    async def predict(self, feature_timeline: dict, window: PredictionWindow) -> Prediction:
        ...


class RenalDeteriorationPlugin(BasePredictionPlugin):
    """
    Plugin : prédiction de détérioration rénale.
    Features : créatinine trend, urée, diurèse, protéinurie.

    TODO : remplacer le score placeholder par un vrai modèle entraîné.
    """

    name = "renal-deterioration-v1"
    supported_windows = [PredictionWindow.D30, PredictionWindow.M6]

    async def predict(self, feature_timeline: dict, window: PredictionWindow) -> Prediction:
        if window not in self.supported_windows:
            raise ValueError(f"Window {window} non supportée par {self.name}")

        # TODO: extraire features réelles
        creatinine_values = [
            lab["value"] for lab in feature_timeline.get("labs", [])
            if lab.get("test") == "creatinine"
        ]

        # Score placeholder (à remplacer par modèle ML)
        score = self._compute_score(creatinine_values, window)
        band = self._score_to_band(score)

        # Claims avec preuves (placeholder)
        claims = []
        if score > 0.5 and creatinine_values:
            claim = Claim(
                claim_id=uuid4(),
                type=ClaimType.ALERT,
                text=f"Risque {'élevé' if score > 0.7 else 'modéré'} de détérioration rénale ({window.value})",
                criticality=CriticalityLevel.HIGH if score > 0.7 else CriticalityLevel.MODERATE,
                evidence_refs=[],  # TODO: ajouter LabEvidenceRef avec vraie valeur créatinine
                # → sera bloqué par EvidenceGuard si evidence_refs reste vide
            )
            claims.append(claim)

        return Prediction(
            patient_id=feature_timeline["patient_id"],
            model=self.name,
            model_version="1.0.0",
            window=window,
            score=score,
            band=band,
            top_factors=[
                PredictionFactor(
                    feature="creatinine_trend",
                    contribution=0.6,
                    direction="positive",
                )
            ],
            claims=claims,
            feature_snapshot=feature_timeline,
        )

    def _compute_score(self, creatinine_values: list, window: PredictionWindow) -> float:
        """Score placeholder — à remplacer par modèle ML entraîné."""
        if not creatinine_values:
            return 0.1
        last = creatinine_values[-1] if creatinine_values else 0
        # Règle simple : créatinine > 2.0 mg/dL = risque élevé
        return min(float(last) / 3.0, 1.0) if last else 0.1

    def _score_to_band(self, score: float) -> RiskBand:
        if score >= 0.75:
            return RiskBand.CRITICAL
        elif score >= 0.5:
            return RiskBand.HIGH
        elif score >= 0.25:
            return RiskBand.MODERATE
        return RiskBand.LOW

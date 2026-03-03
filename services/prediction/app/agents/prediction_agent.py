"""PredictionAgent — Scores longitudinaux via plugins."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.models import Prediction, PredictionWindow, RiskBand

logger = structlog.get_logger(__name__)


class PredictionAgent:
    """
    Écoute : medgemma.completed
    Fait : calcule scores 30d/6m/1y/2y via plugins
    Publie : prediction.completed (avec claims sourcés)
    """

    TOPIC = "medgemma.completed"
    GROUP = "prediction-agent-group"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"prediction-{uuid.uuid4().hex[:8]}"
        self.running = False
        self._plugins: list = []

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        self._load_plugins()
        logger.info("prediction_agent.started", plugins=len(self._plugins))

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id
                )
                for msg_id, event in messages:
                    await self._process(msg_id, event)
            except Exception as e:
                logger.error("prediction_agent.error", error=str(e))
                await asyncio.sleep(5)

    def _load_plugins(self):
        """Charger les plugins de prédiction disponibles."""
        # TODO: auto-découverte des plugins
        from ..plugins.renal_deterioration import RenalDeteriorationPlugin
        self._plugins = [RenalDeteriorationPlugin()]
        logger.info("prediction_agent.plugins_loaded", count=len(self._plugins))

    async def _process(self, msg_id: str, event):
        patient_id = event.payload.get("patient_id")
        logger.info("prediction_agent.processing", patient_id=patient_id)

        # TODO: extraire FeatureTimeline depuis DB
        feature_timeline = await self._extract_features(patient_id)

        all_predictions = []
        for plugin in self._plugins:
            for window in PredictionWindow:
                try:
                    prediction = await plugin.predict(feature_timeline, window)
                    all_predictions.append(prediction)
                except Exception as e:
                    logger.error("prediction_agent.plugin_error", plugin=plugin.name, error=str(e))

        claims = [c for p in all_predictions for c in p.claims]
        await self.event_bus.publish(
            "prediction.completed",
            {
                "patient_id": patient_id,
                "predictions": [p.model_dump(mode="json") for p in all_predictions],
                "claims": [c.model_dump(mode="json") for c in claims],
                "job_id": event.payload.get("job_id"),
            },
            source="prediction",
            correlation_id=event.correlation_id,
        )
        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

    async def _extract_features(self, patient_id: str) -> dict:
        """Extraire FeatureTimeline depuis DB."""
        # TODO: implémenter
        return {"patient_id": patient_id, "labs": [], "findings": [], "medications": []}

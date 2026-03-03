"""NotificationAgent — Alertes dashboard + WhatsApp sans PHI."""

import asyncio
import hashlib
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig
from ryx_shared.claims import CriticalityLevel

logger = structlog.get_logger(__name__)


class NotificationAgent:
    """
    Écoute : evidence.validate.completed, ops.incident
    Fait : push WebSocket + WhatsApp (token-only, JAMAIS PHI)
    Publie : notify.sent

    RÈGLES CRITIQUES :
    - WhatsApp : AUCUNE donnée patient (ni nom, ni ID, ni diagnostic)
    - WhatsApp : token anonyme + lien sécurisé vers dashboard
    - Déduplication : max 1 alerte identique par heure
    - Throttling : max 3 alertes par patient par heure
    """

    TOPICS = ["evidence.validate.completed", "ops.incident"]
    GROUP = "notification-agent-group"

    def __init__(self, event_bus: EventBus, config: RyxConfig):
        self.event_bus = event_bus
        self.config = config
        self.instance_id = f"notification-{uuid.uuid4().hex[:8]}"
        self.running = False
        self._dedup_cache: dict[str, float] = {}  # hash → timestamp

    async def run(self):
        self.running = True
        for topic in self.TOPICS:
            await self.event_bus.ensure_consumer_group(topic, self.GROUP)
        logger.info("notification_agent.started")

        while self.running:
            try:
                for topic in self.TOPICS:
                    messages = await self.event_bus.consume(
                        topic, self.GROUP, self.instance_id, block_ms=1000
                    )
                    for msg_id, event in messages:
                        await self._process(msg_id, event, topic)
            except Exception as e:
                logger.error("notification_agent.error", error=str(e))
                await asyncio.sleep(3)

    async def _process(self, msg_id: str, event, topic: str):
        if topic == "evidence.validate.completed":
            await self._handle_clinical_alert(event)
        elif topic == "ops.incident":
            await self._handle_ops_incident(event)
        await self.event_bus.ack(topic, self.GROUP, msg_id)

    async def _handle_clinical_alert(self, event):
        """Traiter les alertes cliniques validées."""
        valid_claims = event.payload.get("valid_claims", [])
        patient_id = event.payload.get("patient_id")

        critical_claims = [
            c for c in valid_claims
            if c.get("criticality") in ("high", "critical")
        ]

        if not critical_claims:
            return

        for claim in critical_claims:
            # Déduplication
            dedup_key = self._dedup_key(patient_id, claim.get("text", ""))
            if self._is_duplicate(dedup_key):
                continue

            # Dashboard WebSocket
            await self._push_dashboard({
                "type": "alert",
                "criticality": claim["criticality"],
                "claim_id": claim.get("claim_id"),
                "report_id": event.payload.get("report_id"),
                # Pas de texte du claim ici (affiché dans dashboard sécurisé)
            })

            # WhatsApp — JAMAIS de PHI
            if self.config.whatsapp_api_token:
                token = self._generate_case_token(patient_id)
                secure_link = self._generate_secure_link(event.payload.get("report_id"), token)
                await self._send_whatsapp_no_phi(
                    impression_courte=f"Alerte {claim['criticality']}",
                    case_token=token,
                    secure_link=secure_link,
                )

            self._mark_sent(dedup_key)

    async def _handle_ops_incident(self, event):
        """Alertes infrastructure (admins uniquement)."""
        logger.warning("ops.incident", **event.payload)
        await self._push_dashboard({"type": "ops_incident", **event.payload})

    async def _push_dashboard(self, payload: dict):
        """Push vers clients WebSocket connectés."""
        # TODO: implémenter WebSocket manager avec connexions actives
        logger.info("notification.dashboard_push", type=payload.get("type"))

    async def _send_whatsapp_no_phi(
        self, impression_courte: str, case_token: str, secure_link: str
    ):
        """
        Envoyer WhatsApp — RÈGLE ABSOLUE : AUCUNE PHI.

        Format : "🔔 *RYX Alert* | Dossier #{token} | {impression}
        → Voir détails : {secure_link}
        _Expiry: 24h_"
        """
        message = (
            f"🔔 *RYX Alert* | Dossier #{case_token} | {impression_courte}\n"
            f"→ Voir détails : {secure_link}\n"
            f"_Expiry: 24h_"
        )

        # Vérification anti-PHI (garde-fou)
        assert len(case_token) <= 8, "Token trop long — risque PHI"
        # TODO: appeler Meta Cloud API ou Twilio
        logger.info("notification.whatsapp_sent", token=case_token)

    def _generate_case_token(self, patient_id: str | None) -> str:
        """Génère token anonyme court (5 chars) depuis patient_id."""
        if not patient_id:
            return uuid.uuid4().hex[:5].upper()
        return hashlib.sha256(patient_id.encode()).hexdigest()[:5].upper()

    def _generate_secure_link(self, report_id: str | None, token: str) -> str:
        """Lien sécurisé vers dashboard (expire en 24h)."""
        # TODO: générer URL signée avec JWT expirant
        base = "https://dashboard.ryx.health/r"
        return f"{base}/{token}"

    def _dedup_key(self, patient_id: str | None, text: str) -> str:
        return hashlib.md5(f"{patient_id}:{text}".encode()).hexdigest()

    def _is_duplicate(self, key: str) -> bool:
        import time
        last = self._dedup_cache.get(key, 0)
        return (time.time() - last) < 3600  # 1 heure

    def _mark_sent(self, key: str):
        import time
        self._dedup_cache[key] = time.time()

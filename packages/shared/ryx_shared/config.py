"""RYX Configuration — Settings partagés entre tous les services."""

from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class RyxMode(str, Enum):
    HUB = "hub"
    EDGE = "edge"
    HYBRID = "hybrid"


class RyxEnv(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class RyxConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Mode de déploiement
    ryx_mode: RyxMode = RyxMode.HUB
    ryx_env: RyxEnv = RyxEnv.DEVELOPMENT

    # Base de données
    database_url: str = "postgresql+asyncpg://ryx:ryx@localhost:5432/ryx"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream_maxlen: int = 10000  # max events dans un stream

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "ryxdev"
    minio_secret_key: str = "ryxdev123"
    minio_secure: bool = False
    minio_bucket_documents: str = "ryx-documents"
    minio_bucket_dicom: str = "ryx-dicom"
    minio_bucket_models: str = "ryx-models"

    # Meilisearch
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_key: str = ""

    # Orthanc (DICOM)
    orthanc_url: str = "http://localhost:8042"
    orthanc_username: str = "orthanc"
    orthanc_password: str = "orthanc"

    # Auth
    jwt_secret_key: str = "change-me-in-production-use-32-chars-minimum"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # WhatsApp
    whatsapp_api_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = ""

    # Modèles IA
    medgemma_model_path: str = "/models/medgemma-1.5"
    medgemma_onnx_path: str = "/models/edge/medgemma-int8.onnx"
    pillar0_model_path: str = "/models/pillar-0"
    onnx_edge_model_path: str = "/models/edge/"

    # Knowledge Pack
    knowledge_pack_path: str = "/data/knowledge-pack"
    knowledge_pack_version: str = "unknown"

    # Service URLs (pour communication inter-service)
    gateway_url: str = "http://gateway:8000"
    patient_service_url: str = "http://patient:8001"
    ingestion_service_url: str = "http://ingestion:8002"
    preprocess_service_url: str = "http://preprocess:8003"
    imaging_service_url: str = "http://imaging:8004"
    inference_service_url: str = "http://inference:8005"
    evidence_service_url: str = "http://evidence:8006"
    prediction_service_url: str = "http://prediction:8007"
    search_service_url: str = "http://search:8008"
    integration_service_url: str = "http://integration:8009"
    notification_service_url: str = "http://notification:8010"

    @property
    def is_edge(self) -> bool:
        return self.ryx_mode in (RyxMode.EDGE, RyxMode.HYBRID)

    @property
    def is_hub(self) -> bool:
        return self.ryx_mode in (RyxMode.HUB, RyxMode.HYBRID)

    @property
    def is_production(self) -> bool:
        return self.ryx_env == RyxEnv.PRODUCTION

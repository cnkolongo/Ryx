"""MinIO storage client pour l'ingestion."""

from minio import Minio
from minio.error import S3Error
import structlog

from ryx_shared.config import RyxConfig

logger = structlog.get_logger(__name__)
config = RyxConfig()

minio_client = Minio(
    config.minio_endpoint,
    access_key=config.minio_access_key,
    secret_key=config.minio_secret_key,
    secure=config.minio_secure,
)

BUCKETS = [
    config.minio_bucket_documents,
    config.minio_bucket_dicom,
]


async def init_minio():
    """Créer les buckets MinIO si inexistants."""
    for bucket in BUCKETS:
        try:
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
                logger.info("minio.bucket_created", bucket=bucket)
        except S3Error as e:
            logger.error("minio.bucket_error", bucket=bucket, error=str(e))


async def upload_document(
    file_data: bytes,
    patient_id: str,
    doc_id: str,
    filename: str,
    content_type: str,
) -> str:
    """
    Upload un document dans MinIO.
    Retourne le storage_path (bucket/patient_id/doc_id/filename).
    """
    import io
    storage_path = f"{patient_id}/{doc_id}/{filename}"
    minio_client.put_object(
        bucket_name=config.minio_bucket_documents,
        object_name=storage_path,
        data=io.BytesIO(file_data),
        length=len(file_data),
        content_type=content_type,
    )
    return f"{config.minio_bucket_documents}/{storage_path}"

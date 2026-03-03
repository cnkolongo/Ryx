"""OCR Engine — EasyOCR + Tesseract fallback."""

import structlog
from ryx_shared.models import OcrBlock, BoundingBox

logger = structlog.get_logger(__name__)

# Langues supportées (EasyOCR)
SUPPORTED_LANGUAGES = ["fr", "en"]


async def run_ocr(file_data: bytes, mime_type: str = "application/pdf") -> list[OcrBlock]:
    """
    Lance l'OCR sur un document.

    Pipeline :
    1. Si PDF → extraire pages avec PyMuPDF
    2. Pour chaque page → EasyOCR
    3. Si confidence trop basse → Tesseract fallback
    4. Retourner blocs avec bbox normalisées

    EDGE-COMPATIBLE : EasyOCR fonctionne offline.
    """
    # TODO: implémenter selon mime_type
    if mime_type == "application/pdf":
        return await _ocr_pdf(file_data)
    else:
        return await _ocr_image(file_data)


async def _ocr_pdf(file_data: bytes) -> list[OcrBlock]:
    """OCR d'un PDF page par page."""
    import fitz  # PyMuPDF
    import io
    from PIL import Image

    blocks: list[OcrBlock] = []
    doc = fitz.open(stream=file_data, filetype="pdf")

    for page_num, page in enumerate(doc, start=1):
        # Rendre la page en image (300 DPI)
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")

        page_blocks = await _ocr_image_bytes(img_data, page=page_num, width=pix.width, height=pix.height)
        blocks.extend(page_blocks)

    doc.close()
    return blocks


async def _ocr_image(file_data: bytes) -> list[OcrBlock]:
    return await _ocr_image_bytes(file_data, page=1, width=1, height=1)


async def _ocr_image_bytes(
    img_data: bytes, page: int, width: int, height: int
) -> list[OcrBlock]:
    """OCR d'une image avec EasyOCR."""
    try:
        import easyocr
        import numpy as np
        import cv2

        reader = easyocr.Reader(SUPPORTED_LANGUAGES, gpu=False)
        img_array = np.frombuffer(img_data, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        results = reader.readtext(img)
        blocks = []

        for i, (bbox_pts, text, confidence) in enumerate(results):
            # Normaliser bbox [0, 1]
            x_coords = [p[0] for p in bbox_pts]
            y_coords = [p[1] for p in bbox_pts]
            bbox = BoundingBox(
                x1=min(x_coords) / max(width, 1),
                y1=min(y_coords) / max(height, 1),
                x2=max(x_coords) / max(width, 1),
                y2=max(y_coords) / max(height, 1),
            )
            blocks.append(OcrBlock(
                block_id=f"p{page}-b{i}",
                page=page,
                bbox=bbox,
                text=text.strip(),
                confidence=float(confidence),
            ))

        return blocks

    except Exception as e:
        logger.warning("ocr.easyocr_failed", error=str(e), page=page)
        # TODO: Tesseract fallback
        return []

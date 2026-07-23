"""Captcha OCR recognition using ddddocr."""

import base64
import io
import logging

from PIL import Image, ImageFilter, ImageOps

_LOGGER = logging.getLogger(__name__)

_ocr_instance = None


def _get_ocr():
    """Get or create ddddocr instance (lazy load)."""
    global _ocr_instance
    if _ocr_instance is None:
        try:
            import ddddocr
            _ocr_instance = ddddocr.DdddOcr(show_ad=False, beta=True)
            _LOGGER.info("ddddocr initialized (beta model)")
        except ImportError:
            _LOGGER.warning("ddddocr not installed, captcha auto-recognition disabled")
            return None
        except Exception as err:
            _LOGGER.error("Failed to initialize ddddocr: %s", err)
            return None
    return _ocr_instance


def _preprocess(img_bytes: bytes) -> bytes:
    """Preprocess captcha image: grayscale -> binary -> denoise."""
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.grayscale(img)
    img = img.point(lambda x: 255 if x > 128 else 0)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def recognize_captcha(img_base64: str) -> str | None:
    """Recognize 4-char alphanumeric captcha from base64 image.

    Args:
        img_base64: Base64 encoded captcha image (JPEG/PNG)

    Returns:
        Recognized text (4 chars) or None if recognition failed
    """
    ocr = _get_ocr()
    if ocr is None:
        return None

    try:
        img_bytes = base64.b64decode(img_base64)
        processed = _preprocess(img_bytes)
        result = ocr.classification(processed)

        if not result:
            return None

        # 5 chars → take first 4 (common OCR overshoot)
        if len(result) == 5:
            result = result[:4]

        # Must be exactly 4 ASCII alphanumeric chars
        if len(result) == 4 and result.isascii() and result.isalnum():
            _LOGGER.info("Captcha recognized: %s", result)
            return result

        _LOGGER.debug("Captcha rejected: %s", result)
        return None
    except Exception as err:
        _LOGGER.error("Captcha recognition failed: %s", err)
        return None


def is_available() -> bool:
    """Check if captcha OCR is available."""
    return _get_ocr() is not None

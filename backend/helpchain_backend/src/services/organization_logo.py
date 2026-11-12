"""Validate and normalize organization logos before any persistent storage.

This module deliberately does not write to disk or modify organization records.
Callers must separately enforce organization-scoped authorization.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
import warnings

MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 8_000_000
OUTPUT_SIZE = (256, 256)


class InvalidOrganizationLogo(ValueError):
    """Raised when an uploaded organization logo is invalid."""


def normalize_organization_logo(upload: bytes) -> bytes:
    """Return a sanitized, square PNG, or reject an invalid image.

    Image bytes are decoded and re-encoded, removing embedded metadata.
    A caller should validate access rights and enforce HTTP request size limits.
    """
    if not upload or len(upload) > MAX_LOGO_BYTES:
        raise InvalidOrganizationLogo("Le logo doit faire moins de 2 Mo.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            return _decode_and_normalize(upload)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        if isinstance(exc, InvalidOrganizationLogo):
            raise
        raise InvalidOrganizationLogo("Le fichier image est invalide.") from exc


def _decode_and_normalize(upload: bytes) -> bytes:
    with Image.open(BytesIO(upload)) as image:
        if image.format not in {"PNG", "JPEG", "WEBP"}:
            raise InvalidOrganizationLogo("Format de logo non accepté.")
        if image.width < 1 or image.height < 1:
            raise InvalidOrganizationLogo("Dimensions de logo invalides.")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise InvalidOrganizationLogo("Dimensions de logo trop grandes.")
        image = ImageOps.exif_transpose(image)
        image.load()
        image = image.convert("RGBA")
        image.thumbnail(OUTPUT_SIZE, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", OUTPUT_SIZE, (255, 255, 255, 0))
        canvas.alpha_composite(
            image,
            ((OUTPUT_SIZE[0] - image.width) // 2,
             (OUTPUT_SIZE[1] - image.height) // 2),
        )
        output = BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        return output.getvalue()

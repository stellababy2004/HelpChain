from io import BytesIO

import pytest
from PIL import Image

from backend.helpchain_backend.src.services.organization_logo import (
    InvalidOrganizationLogo,
    MAX_LOGO_BYTES,
    normalize_organization_logo,
)


def _image(format="PNG", size=(60, 30)):
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_normalizes_supported_images(format):
    result = normalize_organization_logo(_image(format))
    with Image.open(BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (256, 256)


@pytest.mark.parametrize("payload", [b"", b"not an image", b"x" * (MAX_LOGO_BYTES + 1)])
def test_rejects_invalid_payload(payload):
    with pytest.raises(InvalidOrganizationLogo):
        normalize_organization_logo(payload)


def test_rejects_oversized_dimensions():
    with pytest.raises(InvalidOrganizationLogo):
        normalize_organization_logo(_image(size=(4000, 3000)))

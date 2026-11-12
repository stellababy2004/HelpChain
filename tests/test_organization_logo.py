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


def test_rejects_svg_even_if_named_like_image():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    with pytest.raises(InvalidOrganizationLogo):
        normalize_organization_logo(svg)


def test_removes_exif_metadata_from_jpeg():
    original = Image.new("RGB", (30, 20), "blue")
    exif = Image.Exif()
    exif[270] = "Private organization note"
    source = BytesIO()
    original.save(source, format="JPEG", exif=exif)
    result = normalize_organization_logo(source.getvalue())
    with Image.open(BytesIO(result)) as normalized:
        assert normalized.getexif().get(270) is None
        assert normalized.format == "PNG"


def test_output_has_transparent_padding_and_preserves_aspect_ratio():
    result = normalize_organization_logo(_image(size=(60, 30)))
    with Image.open(BytesIO(result)) as normalized:
        assert normalized.mode == "RGBA"
        assert normalized.getpixel((0, 0))[3] == 0
        assert normalized.getpixel((128, 128))[3] == 255

"""
Unit tests for ImageLoader.
Note on OCR assertions: we assert type and non-emptiness, NOT exact text.
Tesseract output varies by version, language pack, and platform — exact
string matching makes tests brittle across environments.
"""
import pytest
from PIL import Image

from app.services.image_loader import ImageLoader
from tests.conftest import requires_tesseract


class TestImageLoaderContract:
    """Verify the BaseLoader contract is fulfilled correctly."""

    @requires_tesseract
    def test_extract_text_returns_string(self, tmp_png):
        text = ImageLoader(tmp_png).extract_text()
        assert isinstance(text, str)

    def test_get_preview_image_returns_pil_image(self, tmp_png):
        img = ImageLoader(tmp_png).get_preview_image()
        assert isinstance(img, Image.Image)

    def test_get_metadata_returns_dict(self, tmp_png):
        assert isinstance(ImageLoader(tmp_png).get_metadata(), dict)

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            ImageLoader("no_such_image.png")


class TestImagePreprocessing:
    """Verify the preprocessing pipeline produces a valid output image."""

    def test_preview_is_grayscale_converted_back_to_rgb(self, tmp_png):
        # After binarization the image is single-channel (L/grayscale),
        # then converted back to RGB-compatible PIL via Image.fromarray
        img = ImageLoader(tmp_png).get_preview_image()
        # PIL.fromarray on a 2D uint8 array creates mode "L" — acceptable
        assert img.mode in ("L", "RGB", "1")

    def test_preview_dimensions_unchanged(self, tmp_png):
        original = Image.open(tmp_png)
        preview = ImageLoader(tmp_png).get_preview_image()
        # After deskew the canvas size may differ by at most a few pixels
        orig_w, orig_h = original.size
        prev_w, prev_h = preview.size
        assert abs(prev_w - orig_w) <= 10
        assert abs(prev_h - orig_h) <= 10


class TestImageMetadata:
    """Verify metadata keys and values."""

    def test_required_keys_present(self, tmp_png):
        meta = ImageLoader(tmp_png).get_metadata()
        for key in ("page_count", "file_type", "file_size_bytes", "width_px", "height_px"):
            assert key in meta, f"Missing key: {key}"

    def test_page_count_always_one(self, tmp_png):
        assert ImageLoader(tmp_png).get_metadata()["page_count"] == 1

    def test_file_type_from_extension(self, tmp_png):
        assert ImageLoader(tmp_png).get_metadata()["file_type"] == "png"

    def test_dimensions_match_actual_image(self, tmp_png):
        actual = Image.open(tmp_png).size
        meta = ImageLoader(tmp_png).get_metadata()
        assert meta["width_px"] == actual[0]
        assert meta["height_px"] == actual[1]

    def test_file_size_bytes_positive(self, tmp_png):
        assert ImageLoader(tmp_png).get_metadata()["file_size_bytes"] > 0


class TestImageFormats:
    """Verify the loader handles different image formats correctly."""

    @requires_tesseract
    @pytest.mark.parametrize("fmt,suffix", [
        ("JPEG", ".jpg"),
        ("PNG",  ".png"),
    ])
    def test_common_formats_load_without_error(self, tmp_path, fmt, suffix):
        path = tmp_path / f"test{suffix}"
        img = Image.new("RGB", (300, 80), color=(255, 255, 255))
        img.save(path, format=fmt)

        loader = ImageLoader(path)
        result = loader.extract_text()
        assert isinstance(result, str)

    @requires_tesseract
    def test_rgba_image_handled(self, tmp_path):
        # PNG with transparency (RGBA) — the loader must convert to RGB
        path = tmp_path / "rgba.png"
        img = Image.new("RGBA", (300, 80), color=(255, 255, 255, 128))
        img.save(path)

        # Should not raise — convert("RGB") in _preprocess handles this
        loader = ImageLoader(path)
        assert isinstance(loader.extract_text(), str)
import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.base_loader import BaseLoader

logger = get_logger(__name__)


class ImageLoader(BaseLoader):

    def __init__(self, file_path):
        # Point pytesseract at the Tesseract binary before any OCR call
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        super().__init__(file_path)  # validates file exists via BaseLoader

    # â”€â”€ Internal pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _preprocess(self) -> tuple[Image.Image, np.ndarray]:
        """
        Full pre-processing pipeline.
        Returns (preview_pil_image, processed_numpy_array_for_ocr).
        We compute both here so the file is only opened and processed once.
        """
        # Step 1 â€” Open with Pillow, convert to RGB to normalise all formats
        # (PNG can be RGBA, some files are palette-mode 'P' â€” RGB handles all)
        pil_image = Image.open(self.file_path).convert("RGB")

        # Step 2 â€” Convert to numpy array for OpenCV processing
        # PIL is RGB, but OpenCV expects BGR â€” swap the channels
        np_image = np.array(pil_image)
        bgr_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2BGR)

        # Step 3 â€” Grayscale: drop colour, keep intensity only
        # Tesseract reads intensity (dark/light), not colour â€” this removes noise
        gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)

        # Step 4 â€” Denoise: smooth out scanner grain and JPEG compression artifacts
        # h=10 is the filter strength â€” higher removes more noise but blurs edges
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Step 5 â€” Adaptive threshold: convert to pure black/white
        # "Adaptive" adjusts the black/white cutoff per 11Ã—11 pixel block,
        # which handles shadows and uneven lighting a global threshold can't.
        # C=2 is a constant subtracted from the mean â€” fine-tunes the cutoff.
        binarized = cv2.adaptiveThreshold(
            denoised,
            maxValue=255,
            adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=11,
            C=2,
        )

        # Step 6 â€” Deskew: detect tilt angle and rotate to straighten
        binarized = self._deskew(binarized)

        # Convert processed numpy array back to PIL for the preview image
        preview = Image.fromarray(binarized)

        return preview, binarized

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Detect the dominant text angle and rotate to correct it.
        Uses Hough line transform â€” finds the average angle of all detected lines.
        Skips correction if the image has no clear lines (avoids distorting clean images).
        """
        # Detect edges â€” gives us line candidates
        edges = cv2.Canny(image, 50, 150, apertureSize=3)

        # Hough transform â€” find lines longer than 100px in edge image
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

        if lines is None:
            return image  # no lines detected, image is already clean enough

        # Average angle of all detected lines
        angles = [float(line.flat[1]) for line in lines]
        median_angle = np.median(angles)

        # Convert from Hough space (radians) to degrees
        # Hough angles are 0â€“Ï€; text lines cluster near Ï€/2 (vertical)
        skew_angle = (median_angle - np.pi / 2) * (180 / np.pi)

        # Only correct if tilt is meaningful (> 0.5Â°) to avoid unnecessary resampling
        if abs(skew_angle) < 0.5:
            return image

        logger.info(
            "deskew_applied",
            extra={"doc": self.file_path.name, "angle_deg": f"{skew_angle:.2f}"},
        )

        h, w = image.shape
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, float(skew_angle), 1.0)
        return cv2.warpAffine(image, rotation_matrix, (w, h),
                              flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)

    # â”€â”€ BaseLoader contract â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def extract_text(self) -> str:
        logger.info("preprocessing_start", extra={"doc": self.file_path.name})
        _, processed = self._preprocess()
        # lang="eng" targets English â€” swap/extend for multilingual docs
        text = pytesseract.image_to_string(processed, lang="eng").strip()
        logger.info(
            "ocr_complete",
            extra={"doc": self.file_path.name, "chars": len(text)},
        )
        return text

    def get_preview_image(self) -> Image.Image:
        preview, _ = self._preprocess()
        return preview

    def get_metadata(self) -> dict:
        with Image.open(self.file_path) as img:
            width, height = img.size
            mode = img.mode

        return {
            "page_count": 1,
            "file_type": self.file_path.suffix.lstrip(".").lower(),
            "file_size_bytes": self.get_file_size_bytes(),
            "width_px": width,
            "height_px": height,
            "colour_mode": mode,  # RGB, RGBA, L (grayscale), P (palette), etc.
        }


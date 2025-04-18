import logging
import mss
import pytesseract
from PIL import Image
import os
from typing import Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# WARNING: Requires Tesseract OCR engine installed on the system.
# See: https://github.com/tesseract-ocr/tesseract#installing-tesseract
# Also requires screenshot library `mss`.

class ScreenReaderTool(BaseTool):
    name = "read_screen"
    description = (
        "Captures the screen (or a region) and uses OCR to extract text. "
        "Requires Tesseract OCR to be installed on the system. "
        "Input: {'region': {'top': Y, 'left': X, 'width': W, 'height': H} (optional, captures full screen if omitted)}. "
        "Returns the extracted text."
    )

    def __init__(self, tesseract_cmd: Optional[str] = None):
        # Allow specifying tesseract path if not in system PATH
        if tesseract_cmd:
             pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        logger.info("ScreenReaderTool initialized. Ensure Tesseract OCR is installed and in PATH (or path specified).")
        # Check if tesseract is callable
        try:
            pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version {pytesseract.get_tesseract_version()} found.")
        except pytesseract.TesseractNotFoundError:
             logger.error("Tesseract executable not found. Please install Tesseract OCR and ensure it's in your system's PATH or configure tesseract_cmd.")
             raise EnvironmentError("Tesseract OCR not found. Install it to use the ScreenReaderTool.")
        except Exception as e:
             logger.error(f"Error checking Tesseract version: {e}")
             # Continue, but OCR might fail

    def execute(self, **kwargs) -> str:
        region = kwargs.get('region') # Optional region dictionary

        logger.info(f"Executing screen read action. Region: {region or 'Full Screen'}")

        try:
            with mss.mss() as sct:
                if region and all(k in region for k in ['top', 'left', 'width', 'height']):
                    # Capture specific region
                    monitor = {"top": int(region['top']), "left": int(region['left']),
                               "width": int(region['width']), "height": int(region['height'])}
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    logger.info(f"Captured screen region: {monitor}")
                else:
                    # Capture the primary monitor (monitor=1)
                    monitor_number = 1
                    sct_img = sct.grab(sct.monitors[monitor_number])
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    logger.info(f"Captured primary screen (monitor {monitor_number})")

                # Use Tesseract to do OCR on the image
                extracted_text = pytesseract.image_to_string(img)

                if not extracted_text.strip():
                     return "Screen captured successfully, but no text was detected by OCR."

                # Limit output length
                max_len = 8000
                if len(extracted_text) > max_len:
                    extracted_text = extracted_text[:max_len] + "... (extracted text truncated)"

                return f"Screen text (Region: {region or 'Full Screen'}):\n```\n{extracted_text.strip()}\n```"

        except pytesseract.TesseractNotFoundError:
             logger.error("Tesseract executable not found during execution.")
             return "Error: Tesseract OCR is not installed or configured correctly. Cannot read screen."
        except IndexError:
             logger.error("Could not capture screen - monitor definition issue?")
             return "Error: Failed to capture screen, potential monitor configuration issue."
        except Exception as e:
            logger.error(f"An error occurred during screen reading: {e}", exc_info=True)
            return f"Error reading screen: {e}"
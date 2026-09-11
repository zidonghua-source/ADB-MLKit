"""On-device multilingual OCR over ADB."""
from .client import ADBMLKit
from .models import ADBMLKitError, Device, OCRResult, TextBlock, TextLine, TextElement
from .models import LANGUAGES, SCRIPTS, script_for_language

__version__ = "0.1.1"
__all__ = ["ADBMLKit", "ADBMLKitError", "Device", "OCRResult", "TextBlock", "TextLine",
           "TextElement", "LANGUAGES", "SCRIPTS", "script_for_language"]

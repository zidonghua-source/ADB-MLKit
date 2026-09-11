"""Typed, lossless wrappers for protocol-v1 OCR results."""
from dataclasses import dataclass, field, asdict
import json
from typing import Any


class ADBMLKitError(RuntimeError):
    """Transport, device selection, protocol or OCR error."""


SCRIPTS = ("latin", "chinese", "devanagari", "japanese", "korean")
LANGUAGES = {
    "vi": "latin", "en": "latin", "fr": "latin", "de": "latin",
    "es": "latin", "it": "latin", "pt": "latin", "id": "latin",
    "ms": "latin", "tr": "latin", "nl": "latin", "pl": "latin",
    "zh": "chinese", "zh-hans": "chinese", "zh-hant": "chinese",
    "ja": "japanese", "ko": "korean", "hi": "devanagari",
    "mr": "devanagari", "ne": "devanagari",
}


def script_for_language(language: str) -> str:
    """Resolve a documented convenience alias; this is not language detection."""
    key = language.lower().replace("_", "-")
    if key not in LANGUAGES:
        raise ValueError(f"Unsupported language alias {language!r}; choose a script explicitly.")
    return LANGUAGES[key]


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    details: str = ""


@dataclass
class TextElement:
    text: str
    bounds: list[int] | None = None
    corner_points: list[list[int]] = field(default_factory=list)
    recognized_language: str = ""
    confidence: float | None = None


@dataclass
class TextLine(TextElement):
    elements: list[TextElement] = field(default_factory=list)


@dataclass
class TextBlock(TextElement):
    lines: list[TextLine] = field(default_factory=list)


@dataclass
class OCRResult:
    id: str
    text: str
    script: str
    image: dict[str, Any]
    timing: dict[str, Any]
    blocks: list[TextBlock]
    host_timing: dict[str, float] = field(default_factory=dict)
    schema_version: int = 1
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict, request_id: str) -> "OCRResult":
        if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
                or data.get("schema_version") != 1 or data.get("id") != request_id):
            raise ADBMLKitError("Invalid response version or request ID")
        if data.get("ok") is False:
            error = data.get("error", {})
            if not isinstance(error, dict):
                raise ADBMLKitError("Malformed error response")
            raise ADBMLKitError(f"{error.get('code', 'OCR_FAILED')}: {error.get('message', error)}")
        if data.get("ok") is not True:
            raise ADBMLKitError("Missing success status in response")
        def fields(item):
            return {k: item[k] for k in ("text", "bounds", "corner_points", "recognized_language", "confidence") if k in item}
        try:
            if not isinstance(data["text"], str) or data["script"] not in SCRIPTS:
                raise ValueError("Invalid text/script")
            if not isinstance(data["image"], dict) or not isinstance(data["timing"], dict):
                raise ValueError("Invalid image/timing")
            blocks = []
            for block in data["blocks"]:
                lines = [TextLine(**fields(line), elements=[TextElement(**fields(e)) for e in line["elements"]])
                         for line in block["lines"]]
                blocks.append(TextBlock(**fields(block), lines=lines))
            return cls(data["id"], data["text"], data["script"], data["image"], data["timing"], blocks)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ADBMLKitError(f"Malformed OCR response: {exc}") from exc

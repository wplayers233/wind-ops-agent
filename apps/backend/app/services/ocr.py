from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.providers import build_ocr_provider


@dataclass
class OCRPageResult:
    page: int
    text: str
    blocks: list[dict[str, Any]]
    images: list[dict[str, Any]]
    provider: str = "mock_ocr"
    status: str = "offline_fallback"


class OCRAdapter:
    def __init__(self, provider: str = "auto") -> None:
        self.provider_name = provider
        self._provider, self.mode = build_ocr_provider() if provider == "auto" else build_ocr_provider()

    def analyze_page(self, *, page: int, source: str, text: str, image_bytes: bytes | None = None) -> OCRPageResult:
        normalized = " ".join((text or "").split())
        blocks: list[dict[str, Any]] = []
        images: list[dict[str, Any]] = []
        provider_name = getattr(self._provider, "provider", "mock_ocr")
        status = self.mode
        if image_bytes and self.mode == "remote" and hasattr(self._provider, "chat"):
            prompt = "请执行 dots.OCR，返回 JSON：{text,blocks:[{text,bbox,score}],tables:[...]}. 只返回 JSON。"
            result = self._provider.chat([{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": _data_url(image_bytes)}}]}], response_format={"type": "json_object"})
            provider_name = result.provider
            status = result.status
            parsed = _json_payload(result.payload.get("content", "")) if result.status == "ok" else {}
            normalized = " ".join(str(parsed.get("text", normalized)).split())
            for index, block in enumerate(parsed.get("blocks", []) if isinstance(parsed.get("blocks"), list) else []):
                if not isinstance(block, dict):
                    continue
                blocks.append({"id": f"{Path(source).stem}-p{page}-ocr-{index}", "modality": "ocr", "text": str(block.get("text", "")), "page": page, "source": source, "bbox": _bbox(block.get("bbox")), "score": float(block.get("score", 0.0) or 0.0)})
        if normalized and not blocks:
            blocks.append({"id": f"{Path(source).stem}-p{page}-text", "modality": "ocr", "text": normalized, "page": page, "source": source, "bbox": None, "score": 0.86})
        if image_bytes:
            images.append({"id": f"{Path(source).stem}-p{page}-img", "modality": "image", "caption": f"{Path(source).stem} 第{page}页图像区域", "page": page, "source": source, "bbox": None, "score": 0.72})
        return OCRPageResult(page=page, text=normalized, blocks=blocks, images=images, provider=provider_name, status=status)


def build_ocr_bundle(*, source: str, pages: list[dict[str, Any]], provider: str = "auto") -> list[dict[str, Any]]:
    adapter = OCRAdapter(provider=provider)
    bundle: list[dict[str, Any]] = []
    for page in pages:
        result = adapter.analyze_page(page=int(page.get("page", 1)), source=source, text=str(page.get("content", "")), image_bytes=page.get("image_bytes"))
        regions = list(page.get("regions", [])) + result.blocks + result.images
        bundle.append({**page, "ocr_text": result.text or str(page.get("ocr_text", "")), "regions": regions, "content_type": page.get("content_type") or ("image" if page.get("image_bytes") else "ocr"), "ocr_provider": result.provider, "ocr_status": result.status})
    return bundle


def _data_url(data: bytes, mime: str = "image/png") -> str:
    import base64
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _json_payload(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            return tuple(float(item) for item in value)  # type: ignore[return-value]
        except (TypeError, ValueError):
            return None
    return None
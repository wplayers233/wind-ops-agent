from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.ocr import _data_url
from app.services.providers import build_vision_provider


class VisionAdapter:
    def __init__(self, provider: str = "auto") -> None:
        self._provider, self.mode = build_vision_provider("qwen3_vl")

    def describe(self, *, source: str, page: int, content: str, modality: str, image_bytes: bytes | None = None) -> dict[str, Any]:
        title = Path(source).stem
        if image_bytes and self.mode == "remote" and hasattr(self._provider, "chat"):
            prompt = "请分析风电运维图表或设备结构，严格返回 JSON：caption,entities,relations,tables,equipment_structures。"
            result = self._provider.chat([{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": _data_url(image_bytes)}}]}], response_format={"type": "json_object"})
            parsed = _json_payload(result.payload.get("content", "")) if result.status == "ok" else {}
            if parsed:
                return {"id": f"{title}-p{page}-vision", "modality": modality, "caption": str(parsed.get("caption", "")), "tags": ["qwen3-vl", modality], "entities": parsed.get("entities", []), "relations": parsed.get("relations", []), "tables": parsed.get("tables", []), "equipment_structures": parsed.get("equipment_structures", []), "source": source, "page": page, "score": 0.9, "text": content[:240], "vision_provider": result.provider, "vision_status": result.status}
        if modality in {"diagram", "slide"}:
            caption = f"{title} 第{page}页的结构/流程图示意"
            tags = ["diagram", "structure", "equipment"]
        else:
            caption = f"{title} 第{page}页的图片内容摘要"
            tags = ["image", "caption"]
        return {"id": f"{title}-p{page}-vision", "modality": modality, "caption": caption, "tags": tags, "entities": ["部件", "连接关系", "控制单元"], "relations": ["A -> B", "B -> C"], "tables": [], "equipment_structures": [], "source": source, "page": page, "score": 0.78, "text": content[:240], "vision_provider": getattr(self._provider, "provider", "mock_vision"), "vision_status": self.mode}


def build_visual_enrichment(*, source: str, pages: list[dict[str, Any]], provider: str = "auto") -> list[dict[str, Any]]:
    adapter = VisionAdapter(provider=provider)
    enriched: list[dict[str, Any]] = []
    for page in pages:
        modality = str(page.get("content_type") or "text")
        if modality not in {"image", "diagram", "slide", "ocr", "table"}:
            enriched.append(page)
            continue
        vision = adapter.describe(source=source, page=int(page.get("page", 1)), content=str(page.get("content", "")), modality=modality, image_bytes=page.get("image_bytes"))
        regions = list(page.get("regions", []))
        regions.append({"id": vision["id"], "modality": modality, "caption": vision["caption"], "page": vision["page"], "source": source, "bbox": None, "score": vision["score"]})
        enriched.append({**page, "visual_caption": vision["caption"], "regions": regions, "visual_tags": vision["tags"], "visual_entities": vision["entities"], "visual_relations": vision["relations"], "equipment_structures": vision.get("equipment_structures", []), "vision_provider": vision["vision_provider"], "vision_status": vision["vision_status"]})
    return enriched


def _json_payload(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
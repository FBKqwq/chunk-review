# -*- coding: utf-8 -*-
"""人工复验结果落盘。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from parser import build_review_payload, DataPaths


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def output_path(paths: DataPaths, doc_key: str) -> Path:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    return paths.output_dir / f"{doc_key}.review.json"


def init_review_file(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    payload = build_review_payload(paths, doc_key)
    review_json = {
        "base_info": payload["meta"],
        "extractions": {
            ch["chunk_id"]: {
                "entities": ch["entities"],
                "relationships": ch["relationships"],
            }
            for ch in payload["chunks"]
        },
        "review": {
            ch["chunk_id"]: {
                "chunk_id": ch["chunk_id"],
                "section_title": ch["section_title"],
                "page_start": ch["page_start"],
                "page_end": ch["page_end"],
                "status": "unreviewed",
                "remark": "",
                "updated_at": None,
            }
            for ch in payload["chunks"]
        },
        "schema": {
            "status_enum": ["pass", "error", "unreviewed"],
            "note": "base_info 记录 PDF 级基础信息；extractions 按 chunk_id 存储实体和关系；review 按 chunk_id 存储人工复验状态和备注。",
        },
    }
    save_review_json(paths, doc_key, review_json)
    return review_json


def load_review_json(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    path = output_path(paths, doc_key)
    if not path.exists():
        return init_review_file(paths, doc_key)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_review_json(paths: DataPaths, doc_key: str, data: Dict[str, Any]) -> None:
    path = output_path(paths, doc_key)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_chunk_review(
    paths: DataPaths,
    doc_key: str,
    chunk_id: str,
    status: str,
    remark: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if status not in {"pass", "error"}:
        raise ValueError("status 只能是 pass 或 error")
    data = load_review_json(paths, doc_key)
    data.setdefault("extractions", {})[chunk_id] = {
        "entities": entities,
        "relationships": relationships,
    }
    original_review = data.setdefault("review", {}).get(chunk_id, {"chunk_id": chunk_id})
    original_review.update(
        {
            "status": status,
            "remark": remark or "",
            "updated_at": now_iso(),
        }
    )
    data["review"][chunk_id] = original_review
    save_review_json(paths, doc_key, data)
    return data["review"][chunk_id]

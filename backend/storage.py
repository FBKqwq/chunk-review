# -*- coding: utf-8 -*-
"""人工复验结果落盘。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from parser import (
    LLM_FULL_DOCUMENT_CHUNK_ID,
    build_llm_review_payload,
    build_review_payload,
    build_snorkel_review_payload,
    DataPaths,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def output_path(paths: DataPaths, doc_key: str) -> Path:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    return paths.output_dir / f"{doc_key}.review.json"


def snorkel_output_path(paths: DataPaths, doc_key: str) -> Path:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    return paths.output_dir / f"{doc_key}.snorkel.review.json"


def llm_output_path(paths: DataPaths, doc_key: str) -> Path:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    return paths.output_dir / f"{doc_key}.llm.review.json"


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
            "status_enum": ["0", "1", "unreviewed"],
            "note": "base_info 记录 PDF 级基础信息；extractions 按 chunk_id 存储实体和关系；review 按 chunk_id 存储人工复验状态和备注；status 中 0=通过，1=解析错误。",
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


def normalize_review_status(status: str) -> str:
    if status == "pass":
        return "0"
    if status == "error":
        return "1"
    return status


def save_chunk_review(
    paths: DataPaths,
    doc_key: str,
    chunk_id: str,
    status: str,
    remark: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized = normalize_review_status(status)
    if normalized not in {"0", "1"}:
        raise ValueError("status 只能是 0 或 1")
    data = load_review_json(paths, doc_key)
    data.setdefault("extractions", {})[chunk_id] = {
        "entities": entities,
        "relationships": relationships,
    }
    original_review = data.setdefault("review", {}).get(chunk_id, {"chunk_id": chunk_id})
    original_review.update(
        {
            "status": normalized,
            "remark": remark or "",
            "updated_at": now_iso(),
        }
    )
    data["review"][chunk_id] = original_review
    save_review_json(paths, doc_key, data)
    return data["review"][chunk_id]


def init_snorkel_review_file(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    payload = build_snorkel_review_payload(paths, doc_key)
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
            "status_enum": ["0", "1", "unreviewed"],
            "program": "snorkel",
            "note": "Snorkel entitybase 复验结果；extractions 按 chunk_id 存储实体和关系；review 按 chunk_id 存储人工复验状态。",
        },
    }
    save_snorkel_review_json(paths, doc_key, review_json)
    return review_json


def load_snorkel_review_json(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    path = snorkel_output_path(paths, doc_key)
    if not path.exists():
        return init_snorkel_review_file(paths, doc_key)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_snorkel_review_json(paths: DataPaths, doc_key: str, data: Dict[str, Any]) -> None:
    path = snorkel_output_path(paths, doc_key)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_snorkel_chunk_review(
    paths: DataPaths,
    doc_key: str,
    chunk_id: str,
    status: str,
    remark: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized = normalize_review_status(status)
    if normalized not in {"0", "1"}:
        raise ValueError("status 只能是 0 或 1")
    data = load_snorkel_review_json(paths, doc_key)
    data.setdefault("extractions", {})[chunk_id] = {
        "entities": entities,
        "relationships": relationships,
    }
    original_review = data.setdefault("review", {}).get(chunk_id, {"chunk_id": chunk_id})
    original_review.update(
        {
            "status": normalized,
            "remark": remark or "",
            "updated_at": now_iso(),
        }
    )
    data["review"][chunk_id] = original_review
    save_snorkel_review_json(paths, doc_key, data)
    return data["review"][chunk_id]


def init_llm_review_file(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    payload = build_llm_review_payload(paths, doc_key)
    document_chunk = payload["chunks"][0]
    review_json = {
        "base_info": payload["meta"],
        "extractions": {
            LLM_FULL_DOCUMENT_CHUNK_ID: {
                "entities": document_chunk["entities"],
                "relationships": document_chunk["relationships"],
            }
        },
        "review": {
            LLM_FULL_DOCUMENT_CHUNK_ID: {
                "chunk_id": LLM_FULL_DOCUMENT_CHUNK_ID,
                "section_title": document_chunk.get("section_title", "全文"),
                "page_start": document_chunk.get("page_start"),
                "page_end": document_chunk.get("page_end"),
                "status": "unreviewed",
                "remark": "",
                "updated_at": None,
            }
        },
        "schema": {
            "status_enum": ["0", "1", "unreviewed"],
            "program": "llm",
            "note": "LLM 全文级复验结果；extractions 按文档存储实体和关系；review 存储整份 PDF 复验状态。",
        },
    }
    save_llm_review_json(paths, doc_key, review_json)
    return review_json


def load_llm_review_json(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    path = llm_output_path(paths, doc_key)
    if not path.exists():
        return init_llm_review_file(paths, doc_key)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_llm_review_json(paths: DataPaths, doc_key: str, data: Dict[str, Any]) -> None:
    path = llm_output_path(paths, doc_key)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_llm_document_review(
    paths: DataPaths,
    doc_key: str,
    status: str,
    remark: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized = normalize_review_status(status)
    if normalized not in {"0", "1"}:
        raise ValueError("status 只能是 0 或 1")
    data = load_llm_review_json(paths, doc_key)
    data.setdefault("extractions", {})[LLM_FULL_DOCUMENT_CHUNK_ID] = {
        "entities": entities,
        "relationships": relationships,
    }
    original_review = data.setdefault("review", {}).get(
        LLM_FULL_DOCUMENT_CHUNK_ID,
        {"chunk_id": LLM_FULL_DOCUMENT_CHUNK_ID},
    )
    original_review.update(
        {
            "status": normalized,
            "remark": remark or "",
            "updated_at": now_iso(),
        }
    )
    data["review"][LLM_FULL_DOCUMENT_CHUNK_ID] = original_review
    save_llm_review_json(paths, doc_key, data)
    return data["review"][LLM_FULL_DOCUMENT_CHUNK_ID]

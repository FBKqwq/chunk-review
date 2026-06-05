# -*- coding: utf-8 -*-
"""
解析 data/input/chunk 与 data/input/kg_json 下的结构化 JSON。
职责：
1. 按 PDF 维度配对 chunk.json 与 kg.json。
2. 按 chunk_id 聚合 chunk 原文、实体、关系。
3. 将预抽取英文标签映射为前端固定中文类型。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


ENTITY_TYPES = [
    "疾病",
    "确诊疾病",
    "临床表现",
    "指标",
    "病因",
    "病理生理机制阐述",
    "治疗原则",
    "治疗方案",
]

# 用户要求固定 7 类关系；此处与当前 kg.json 中的 7 类关系保持兼容。
RELATION_TYPES = [
    "has_sub_disease",
    "manifests_as",
    "requires_test",
    "follows_treatment",
    "implements_by",
    "causes",
    "explained_by",
]

LABEL_TO_ENTITY_TYPE = {
    "Symptom": "临床表现",
    "Test": "指标",
    "Disease": "疾病",
    "Sub_Disease": "确诊疾病",
    "Etiology": "病因",  
    "Treatment": "治疗原则",
    "Plan": "治疗方案",
    "Pathogenesis": "病理生理机制阐述",
}

RELATION_LABEL_CN = {
    "has_sub_disease": "包含分型",
    "manifests_as": "表现为",
    "requires_test": "需要指标",
    "follows_treatment": "确定原则",
    "implements_by": "落实方案",
    "causes": "导致",
    "explained_by": "机制解释",
}


@dataclass
class DataPaths:
    base_dir: Path

    @property
    def chunk_dir(self) -> Path:
        return self.base_dir / "data" / "input" / "chunk"

    @property
    def kg_dir(self) -> Path:
        return self.base_dir / "data" / "input" / "kg_json"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "data" / "output"


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def stem_doc_name(path: Path) -> str:
    name = path.name
    for suffix in [".chunk.json", ".kg.json", ".json"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def find_documents(paths: DataPaths) -> List[Dict[str, Any]]:
    """扫描 input 目录，返回可复验文档列表。"""
    docs: List[Dict[str, Any]] = []
    chunk_files = {stem_doc_name(p): p for p in paths.chunk_dir.glob("*.json")}
    kg_files = {stem_doc_name(p): p for p in paths.kg_dir.glob("*.json")}

    for doc_key, chunk_path in sorted(chunk_files.items()):
        kg_path = kg_files.get(doc_key)
        if not kg_path:
            continue
        chunk_json = read_json(chunk_path)
        kg_json = read_json(kg_path)
        docs.append(
            {
                "doc_key": doc_key,
                "doc_id": chunk_json.get("doc_id") or kg_json.get("meta", {}).get("doc_id"),
                "source_title": chunk_json.get("source_title") or kg_json.get("meta", {}).get("source_title"),
                "pdf_path": chunk_json.get("pdf_path") or kg_json.get("meta", {}).get("pdf_path"),
                "total_chunks": len(chunk_json.get("chunks", [])),
                "chunk_file": str(chunk_path),
                "kg_file": str(kg_path),
            }
        )
    return docs


def load_doc(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    chunk_path = paths.chunk_dir / f"{doc_key}.chunk.json"
    kg_path = paths.kg_dir / f"{doc_key}.kg.json"
    if not chunk_path.exists() or not kg_path.exists():
        raise FileNotFoundError(f"找不到配对文件：{chunk_path.name} / {kg_path.name}")
    return {"chunk": read_json(chunk_path), "kg": read_json(kg_path)}


def normalize_entity(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": node.get("id", ""),
        "entity_type": LABEL_TO_ENTITY_TYPE.get(node.get("label"), node.get("label", "")),
        "raw_label": node.get("label", ""),
        "entity_name": node.get("name", ""),
        "chunk_id": node.get("chunk_id", ""),
        "evidence_ids": node.get("evidence_ids", ""),
    }


def normalize_relation(rel: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": rel.get("id", ""),
        "relation_type": rel.get("type", ""),
        "relation_type_cn": RELATION_LABEL_CN.get(rel.get("type", ""), rel.get("type", "")),
        "source_entity": rel.get("from_name", ""),
        "target_entity": rel.get("to_name", ""),
        "source_id": rel.get("from_id", ""),
        "target_id": rel.get("to_id", ""),
        "chunk_id": rel.get("chunk_id", ""),
        "evidence_ids": rel.get("evidence_ids", ""),
    }


def build_review_payload(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    data = load_doc(paths, doc_key)
    chunk_json, kg_json = data["chunk"], data["kg"]
    chunks = chunk_json.get("chunks", [])

    nodes_by_chunk: Dict[str, List[Dict[str, Any]]] = {}
    for node in kg_json.get("nodes", []):
        nodes_by_chunk.setdefault(node.get("chunk_id", ""), []).append(normalize_entity(node))

    rels_by_chunk: Dict[str, List[Dict[str, Any]]] = {}
    for rel in kg_json.get("relationships", []):
        rels_by_chunk.setdefault(rel.get("chunk_id", ""), []).append(normalize_relation(rel))

    review_chunks: List[Dict[str, Any]] = []
    for idx, ch in enumerate(chunks):
        chunk_id = ch.get("chunk_id", "")
        entities = nodes_by_chunk.get(chunk_id, [])
        review_chunks.append(
            {
                "index": idx,
                "chunk_id": chunk_id,
                "section_title": ch.get("section_title", ""),
                "section_path": ch.get("section_path", []),
                "page_start": ch.get("page_start"),
                "page_end": ch.get("page_end"),
                "text_span": ch.get("text_span", {}),
                "text": ch.get("text", ""),
                "entities": entities,
                "relationships": rels_by_chunk.get(chunk_id, []),
                "review": {"status": "", "remark": ""},
            }
        )

    return {
        "meta": {
            "doc_key": doc_key,
            "doc_id": chunk_json.get("doc_id") or kg_json.get("meta", {}).get("doc_id"),
            "source_title": chunk_json.get("source_title") or kg_json.get("meta", {}).get("source_title"),
            "pdf_path": chunk_json.get("pdf_path") or kg_json.get("meta", {}).get("pdf_path"),
            "chunking_method": chunk_json.get("chunking_method"),
            "total_pages": chunk_json.get("total_pages"),
            "total_chunks": len(review_chunks),
        },
        "entity_types": ENTITY_TYPES,
        "relation_types": RELATION_TYPES,
        "relation_type_names": RELATION_LABEL_CN,
        "chunks": review_chunks,
    }

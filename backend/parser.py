# -*- coding: utf-8 -*-
"""
解析 data/input 下的结构化 JSON。
职责：
1. 按程序选择 chunk 目录：OpenTCM 读取 chunk_OpenTCM，snorkel/LLM 读取 chunk_snorkel。
2. 按 PDF 维度配对 chunk.json 与 kg.json。
3. 按 chunk_id 聚合 chunk 原文、实体、关系。
4. 将预抽取英文标签映射为前端固定中文类型。
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

ENTITYBASE_TYPE_TO_CN = {
    "diseases": "疾病",
    "sub_diseases": "确诊疾病",
    "symptoms": "临床表现",
    "tests": "指标",
    "etiologies": "病因",
    "pathogeneses": "病理生理机制阐述",
    "treatments": "治疗原则",
    "plans": "治疗方案",
}


@dataclass
class DataPaths:
    base_dir: Path
    dataset: str = "ALL"

    @property
    def _input_base(self) -> Path:
        return self.base_dir / "data" / self.dataset / "input"

    @property
    def chunk_dir(self) -> Path:
        """旧版默认 chunk 目录，作为新目录缺失时的回退。"""
        return self._input_base / "chunk"

    @property
    def chunk_opentcm_dir(self) -> Path:
        return self._input_base / "chunk_OpenTCM"

    @property
    def chunk_snorkel_dir(self) -> Path:
        return self._input_base / "chunk_snorkel"

    def chunk_dir_for(self, program: str) -> Path:
        """按程序选择 chunk 目录：OpenTCM 用 chunk_OpenTCM，snorkel/LLM 用 chunk_snorkel。"""
        target = self.chunk_opentcm_dir if (program or "").lower() == "opentcm" else self.chunk_snorkel_dir
        if target.exists():
            return target
        return self.chunk_dir

    @property
    def kg_dir(self) -> Path:
        return self._input_base / "kg_json"

    @property
    def entitybase_dir(self) -> Path:
        return self._input_base / "entitybase"

    @property
    def llm_dir(self) -> Path:
        return self._input_base / "LLM"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "data" / self.dataset / "output"


LLM_FULL_DOCUMENT_CHUNK_ID = "__FULL_DOCUMENT__"

LLM_TYPE_TO_CN = {
    **ENTITYBASE_TYPE_TO_CN,
    "pathogenesis": "病理生理机制阐述",
}


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def stem_doc_name(path: Path) -> str:
    name = path.name
    for suffix in [".chunk.json", ".kg.json", ".entity_base.jsonl", ".entity_nodes.jsonl", ".json"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def find_documents(paths: DataPaths, program: str = "opentcm") -> List[Dict[str, Any]]:
    """扫描 input 目录，返回可复验文档列表；优先以 chunk 为准，kg_json 可选。

    OpenTCM 读取 chunk_OpenTCM，snorkel/LLM 读取 chunk_snorkel。
    """
    docs: List[Dict[str, Any]] = []
    chunk_dir = paths.chunk_dir_for(program)
    chunk_files = {stem_doc_name(p): p for p in chunk_dir.glob("*.json")}
    kg_files = {stem_doc_name(p): p for p in paths.kg_dir.glob("*.json")}
    entitybase_files = {}
    for p in paths.entitybase_dir.glob("*.entity_base.jsonl"):
        entitybase_files[stem_doc_name(p)] = p
    for p in paths.entitybase_dir.glob("*.entity_nodes.jsonl"):
        key = stem_doc_name(p)
        if key not in entitybase_files:
            entitybase_files[key] = p
    llm_files = {stem_doc_name(p): p for p in paths.llm_dir.glob("*.json")}

    for doc_key, chunk_path in sorted(chunk_files.items()):
        chunk_json = read_json(chunk_path)
        kg_path = kg_files.get(doc_key)
        kg_json = read_json(kg_path) if kg_path else {}
        entitybase_path = entitybase_files.get(doc_key)
        llm_path = llm_files.get(doc_key)
        docs.append(
            {
                "doc_key": doc_key,
                "doc_id": chunk_json.get("doc_id") or kg_json.get("meta", {}).get("doc_id"),
                "source_title": chunk_json.get("source_title") or kg_json.get("meta", {}).get("source_title"),
                "pdf_path": chunk_json.get("pdf_path") or kg_json.get("meta", {}).get("pdf_path"),
                "total_chunks": len(chunk_json.get("chunks", [])),
                "has_kg": bool(kg_path),
                "has_entitybase": bool(entitybase_path),
                "has_llm": bool(llm_path),
                "chunk_file": str(chunk_path),
                "kg_file": str(kg_path) if kg_path else None,
                "entitybase_file": str(entitybase_path) if entitybase_path else None,
                "llm_file": str(llm_path) if llm_path else None,
            }
        )
    return docs


def load_doc(paths: DataPaths, doc_key: str, program: str = "opentcm") -> Dict[str, Any]:
    chunk_path = paths.chunk_dir_for(program) / f"{doc_key}.chunk.json"
    kg_path = paths.kg_dir / f"{doc_key}.kg.json"
    if not chunk_path.exists():
        raise FileNotFoundError(f"找不到 chunk 文件：{chunk_path.name}")
    return {
        "chunk": read_json(chunk_path),
        "kg": read_json(kg_path) if kg_path.exists() else None,
        "has_kg": kg_path.exists(),
    }


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


def chunk_kg_status(has_kg: bool, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
    if not has_kg:
        return "no_kg_file"
    if entities or relationships:
        return "matched"
    return "empty"


def chunk_entitybase_status(has_entitybase: bool, entities: List[Dict[str, Any]]) -> str:
    if not has_entitybase:
        return "no_entitybase_file"
    if entities:
        return "matched"
    return "empty"


def normalize_entitybase_record(record: Dict[str, Any]) -> Dict[str, Any]:
    raw_type = record.get("entity_type", "")
    return {
        "id": record.get("entity_id", ""),
        "entity_type": ENTITYBASE_TYPE_TO_CN.get(raw_type, raw_type),
        "raw_label": raw_type,
        "entity_name": record.get("name", ""),
        "chunk_id": record.get("chunk_id", ""),
        "evidence_ids": "",
        "confidence": record.get("confidence"),
    }


def _find_entitybase_path(paths: DataPaths, doc_key: str) -> Optional[Path]:
    """在 entitybase 目录中查找指定文档的 entitybase 文件，兼容多种命名后缀。"""
    for suffix in [".entity_base.jsonl", ".entity_nodes.jsonl"]:
        path = paths.entitybase_dir / f"{doc_key}{suffix}"
        if path.exists():
            return path
    return None


def load_entitybase_by_chunk(paths: DataPaths, doc_key: str) -> Dict[str, List[Dict[str, Any]]]:
    path = _find_entitybase_path(paths, doc_key)
    entities_by_chunk: Dict[str, List[Dict[str, Any]]] = {}
    if not path:
        return entities_by_chunk
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            entity = normalize_entitybase_record(record)
            entities_by_chunk.setdefault(entity["chunk_id"], []).append(entity)
    return entities_by_chunk


def build_review_payload(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    data = load_doc(paths, doc_key, program="opentcm")
    chunk_json = data["chunk"]
    kg_json = data["kg"] or {}
    has_kg = data["has_kg"]
    chunks = chunk_json.get("chunks", [])

    nodes_by_chunk: Dict[str, List[Dict[str, Any]]] = {}
    if has_kg:
        for node in kg_json.get("nodes", []):
            nodes_by_chunk.setdefault(node.get("chunk_id", ""), []).append(normalize_entity(node))

    rels_by_chunk: Dict[str, List[Dict[str, Any]]] = {}
    if has_kg:
        for rel in kg_json.get("relationships", []):
            rels_by_chunk.setdefault(rel.get("chunk_id", ""), []).append(normalize_relation(rel))

    review_chunks: List[Dict[str, Any]] = []
    matched_chunk_count = 0
    for idx, ch in enumerate(chunks):
        chunk_id = ch.get("chunk_id", "")
        entities = nodes_by_chunk.get(chunk_id, []) if has_kg else []
        relationships = rels_by_chunk.get(chunk_id, []) if has_kg else []
        kg_status = chunk_kg_status(has_kg, entities, relationships)
        if kg_status == "matched":
            matched_chunk_count += 1
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
                "relationships": relationships,
                "kg_status": kg_status,
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
            "has_kg": has_kg,
            "kg_status": "matched" if has_kg else "missing",
            "kg_matched_chunks": matched_chunk_count,
        },
        "entity_types": ENTITY_TYPES,
        "relation_types": RELATION_TYPES,
        "relation_type_names": RELATION_LABEL_CN,
        "chunks": review_chunks,
    }


def build_snorkel_review_payload(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    data = load_doc(paths, doc_key, program="snorkel")
    chunk_json = data["chunk"]
    chunks = chunk_json.get("chunks", [])
    entitybase_path = _find_entitybase_path(paths, doc_key)
    has_entitybase = entitybase_path is not None
    entities_by_chunk = load_entitybase_by_chunk(paths, doc_key) if has_entitybase else {}

    review_chunks: List[Dict[str, Any]] = []
    matched_chunk_count = 0
    for idx, ch in enumerate(chunks):
        chunk_id = ch.get("chunk_id", "")
        entities = entities_by_chunk.get(chunk_id, []) if has_entitybase else []
        relationships: List[Dict[str, Any]] = []
        entitybase_status = chunk_entitybase_status(has_entitybase, entities)
        if entitybase_status == "matched":
            matched_chunk_count += 1
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
                "relationships": relationships,
                "entitybase_status": entitybase_status,
                "review": {"status": "", "remark": ""},
            }
        )

    return {
        "meta": {
            "doc_key": doc_key,
            "doc_id": chunk_json.get("doc_id"),
            "source_title": chunk_json.get("source_title"),
            "pdf_path": chunk_json.get("pdf_path"),
            "chunking_method": chunk_json.get("chunking_method"),
            "total_pages": chunk_json.get("total_pages"),
            "total_chunks": len(review_chunks),
            "has_entitybase": has_entitybase,
            "entitybase_status": "matched" if has_entitybase else "missing",
            "entitybase_matched_chunks": matched_chunk_count,
            "program": "snorkel",
        },
        "entity_types": ENTITY_TYPES,
        "relation_types": RELATION_TYPES,
        "relation_type_names": RELATION_LABEL_CN,
        "chunks": review_chunks,
    }


def concatenate_chunks_text(chunks: List[Dict[str, Any]]) -> str:
    parts = [(ch.get("text") or "").strip() for ch in chunks]
    return "\n\n".join(part for part in parts if part)


def normalize_llm_entity(entity_type_key: str, entity: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": entity.get("id", ""),
        "entity_type": LLM_TYPE_TO_CN.get(entity_type_key, entity_type_key),
        "raw_label": entity_type_key,
        "entity_name": entity.get("name") or entity.get("content") or "",
        "chunk_id": LLM_FULL_DOCUMENT_CHUNK_ID,
        "evidence_ids": entity.get("evidence_ids", ""),
        "confidence": entity.get("confidence"),
    }


def flatten_llm_entities(llm_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    entity_groups = llm_json.get("entities") or {}
    if not isinstance(entity_groups, dict):
        return entities
    for entity_type_key, items in entity_groups.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                entities.append(normalize_llm_entity(entity_type_key, item))
    return entities


def build_llm_id_name_map(entities: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for entity in entities:
        entity_id = (entity.get("id") or "").strip()
        entity_name = (entity.get("entity_name") or "").strip()
        if entity_id and entity_name:
            mapping[entity_id] = entity_name
    return mapping


def normalize_llm_relation(rel: Dict[str, Any], id_to_name: Dict[str, str]) -> Dict[str, Any]:
    source_id = rel.get("from", "")
    target_id = rel.get("to", "")
    return {
        "id": rel.get("relation_id", ""),
        "relation_type": rel.get("relation_type", ""),
        "relation_type_cn": RELATION_LABEL_CN.get(rel.get("relation_type", ""), rel.get("relation_type", "")),
        "source_entity": id_to_name.get(source_id, source_id),
        "target_entity": id_to_name.get(target_id, target_id),
        "source_id": source_id,
        "target_id": target_id,
        "chunk_id": LLM_FULL_DOCUMENT_CHUNK_ID,
        "evidence_ids": rel.get("evidence_ids", ""),
    }


def flatten_llm_relationships(llm_json: Dict[str, Any], id_to_name: Dict[str, str]) -> List[Dict[str, Any]]:
    relationships: List[Dict[str, Any]] = []
    relation_groups = llm_json.get("relationships") or {}
    if not isinstance(relation_groups, dict):
        return relationships
    for rel_type, items in relation_groups.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            relation = normalize_llm_relation(item, id_to_name)
            if not relation.get("relation_type"):
                relation["relation_type"] = rel_type
            relationships.append(relation)
    return relationships


def build_llm_review_payload(paths: DataPaths, doc_key: str) -> Dict[str, Any]:
    data = load_doc(paths, doc_key, program="llm")
    chunk_json = data["chunk"]
    chunks = chunk_json.get("chunks", [])
    llm_path = paths.llm_dir / f"{doc_key}.json"
    has_llm = llm_path.exists()
    llm_json = read_json(llm_path) if has_llm else {}
    full_text = concatenate_chunks_text(chunks)

    entities = flatten_llm_entities(llm_json) if has_llm else []
    id_to_name = build_llm_id_name_map(entities)
    relationships = flatten_llm_relationships(llm_json, id_to_name) if has_llm else []
    llm_status = "matched" if has_llm and (entities or relationships) else ("missing" if not has_llm else "empty")

    first_page = chunks[0].get("page_start") if chunks else None
    last_page = chunks[-1].get("page_end") if chunks else None
    document_chunk = {
        "index": 0,
        "chunk_id": LLM_FULL_DOCUMENT_CHUNK_ID,
        "section_title": llm_json.get("meta", {}).get("section_path") or "全文",
        "section_path": ["全文"],
        "page_start": first_page,
        "page_end": last_page,
        "text_span": {"start": 0, "end": len(full_text)},
        "text": full_text,
        "entities": entities,
        "relationships": relationships,
        "llm_status": llm_status,
        "review": {"status": "", "remark": ""},
    }

    return {
        "meta": {
            "doc_key": doc_key,
            "doc_id": chunk_json.get("doc_id") or llm_json.get("meta", {}).get("doc_id"),
            "source_title": chunk_json.get("source_title") or llm_json.get("meta", {}).get("source_title"),
            "pdf_path": chunk_json.get("pdf_path"),
            "chunking_method": chunk_json.get("chunking_method"),
            "total_pages": chunk_json.get("total_pages"),
            "total_chunks": len(chunks),
            "concatenated_chunk_count": len(chunks),
            "has_llm": has_llm,
            "llm_status": llm_status,
            "program": "llm",
            "review_mode": "document",
        },
        "entity_types": ENTITY_TYPES,
        "relation_types": RELATION_TYPES,
        "relation_type_names": RELATION_LABEL_CN,
        "chunks": [document_chunk],
    }

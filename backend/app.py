# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from parser import (
    DataPaths,
    LLM_FULL_DOCUMENT_CHUNK_ID,
    build_llm_review_payload,
    build_review_payload,
    build_snorkel_review_payload,
    find_documents,
)
from storage import (
    is_chunk_reviewed,
    llm_output_path,
    load_llm_review_json,
    load_review_json,
    load_snorkel_review_json,
    normalize_review_status,
    output_path,
    save_chunk_review,
    save_llm_document_review,
    save_snorkel_chunk_review,
    snorkel_output_path,
)

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_SRC_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_SRC_DIR / "dist"
FRONTEND_DIR = FRONTEND_DIST_DIR if FRONTEND_DIST_DIR.exists() else FRONTEND_SRC_DIR
DATA_DIR = BASE_DIR / "data"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)


def get_paths() -> DataPaths:
    """根据请求参数动态创建 DataPaths，支持数据集切换。"""
    dataset = request.args.get("dataset", "ALL")
    return DataPaths(BASE_DIR, dataset=dataset)


def _list_available_datasets() -> list:
    """扫描 data/ 目录，返回包含 input 子目录的数据集名称列表。"""
    datasets = []
    if not DATA_DIR.exists():
        return datasets
    for entry in sorted(DATA_DIR.iterdir()):
        if entry.is_dir() and (entry / "input").is_dir():
            datasets.append(entry.name)
    return datasets


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/datasets")
def api_datasets():
    """返回可用的数据集列表。"""
    return jsonify({"datasets": _list_available_datasets()})


@app.get("/api/documents")
def api_documents():
    paths = get_paths()
    program = request.args.get("program", "opentcm")
    return jsonify({"documents": find_documents(paths, program=program)})


@app.get("/api/review-data/<doc_key>")
def api_review_data(doc_key: str):
    paths = get_paths()
    try:
        payload = build_review_payload(paths, doc_key)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    review_file = load_review_json(paths, doc_key)
    review_map = review_file.get("review", {})
    extraction_map = review_file.get("extractions", {})
    for ch in payload["chunks"]:
        chunk_id = ch["chunk_id"]
        if chunk_id in extraction_map:
            ch["entities"] = extraction_map[chunk_id].get("entities", ch["entities"])
            ch["relationships"] = extraction_map[chunk_id].get("relationships", ch["relationships"])
        review = review_map.get(chunk_id, {"status": "unreviewed", "remark": ""})
        if review.get("status") not in ("", "unreviewed", None):
            review = {**review, "status": normalize_review_status(review.get("status", ""))}
        ch["review"] = review
    return jsonify(payload)


@app.post("/api/review-data/<doc_key>/<chunk_id>")
def api_save_chunk(doc_key: str, chunk_id: str):
    paths = get_paths()
    body: Dict[str, Any] = request.get_json(force=True, silent=False)
    result = save_chunk_review(
        paths,
        doc_key=doc_key,
        chunk_id=chunk_id,
        status=body.get("status", ""),
        remark=body.get("remark", ""),
        entities=body.get("entities", []),
        relationships=body.get("relationships", []),
    )
    return jsonify({"ok": True, "review": result})


@app.get("/api/review-output/<doc_key>")
def api_review_output(doc_key: str):
    paths = get_paths()
    data = load_review_json(paths, doc_key)
    return jsonify(data)


@app.get("/api/review-output-file/<doc_key>")
def api_review_output_file(doc_key: str):
    paths = get_paths()
    path = output_path(paths, doc_key)
    if not path.exists():
        load_review_json(paths, doc_key)
    return send_from_directory(path.parent, path.name, as_attachment=True)


@app.get("/api/snorkel-review-data/<doc_key>")
def api_snorkel_review_data(doc_key: str):
    paths = get_paths()
    try:
        payload = build_snorkel_review_payload(paths, doc_key)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    review_file = load_snorkel_review_json(paths, doc_key)
    review_map = review_file.get("review", {})
    extraction_map = review_file.get("extractions", {})
    for ch in payload["chunks"]:
        chunk_id = ch["chunk_id"]
        review = review_map.get(chunk_id, {"status": "unreviewed", "remark": ""})
        if review.get("status") not in ("", "unreviewed", None):
            review = {**review, "status": normalize_review_status(review.get("status", ""))}
        if is_chunk_reviewed(review.get("status", "")) and chunk_id in extraction_map:
            ch["entities"] = extraction_map[chunk_id].get("entities", ch["entities"])
            ch["relationships"] = extraction_map[chunk_id].get("relationships", ch["relationships"])
        ch["review"] = review
    return jsonify(payload)


@app.post("/api/snorkel-review-data/<doc_key>/<chunk_id>")
def api_save_snorkel_chunk(doc_key: str, chunk_id: str):
    paths = get_paths()
    body: Dict[str, Any] = request.get_json(force=True, silent=False)
    result = save_snorkel_chunk_review(
        paths,
        doc_key=doc_key,
        chunk_id=chunk_id,
        status=body.get("status", ""),
        remark=body.get("remark", ""),
        entities=body.get("entities", []),
        relationships=body.get("relationships", []),
    )
    return jsonify({"ok": True, "review": result})


@app.get("/api/snorkel-review-output-file/<doc_key>")
def api_snorkel_review_output_file(doc_key: str):
    paths = get_paths()
    path = snorkel_output_path(paths, doc_key)
    if not path.exists():
        load_snorkel_review_json(paths, doc_key)
    return send_from_directory(path.parent, path.name, as_attachment=True)


@app.get("/api/llm-review-data/<doc_key>")
def api_llm_review_data(doc_key: str):
    paths = get_paths()
    try:
        payload = build_llm_review_payload(paths, doc_key)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    review_file = load_llm_review_json(paths, doc_key)
    review_map = review_file.get("review", {})
    extraction_map = review_file.get("extractions", {})
    for ch in payload["chunks"]:
        chunk_id = ch["chunk_id"]
        if chunk_id in extraction_map:
            ch["entities"] = extraction_map[chunk_id].get("entities", ch["entities"])
            ch["relationships"] = extraction_map[chunk_id].get("relationships", ch["relationships"])
        review = review_map.get(chunk_id, {"status": "unreviewed", "remark": ""})
        if review.get("status") not in ("", "unreviewed", None):
            review = {**review, "status": normalize_review_status(review.get("status", ""))}
        ch["review"] = review
    return jsonify(payload)


@app.post("/api/llm-review-data/<doc_key>")
def api_save_llm_document(doc_key: str):
    paths = get_paths()
    body: Dict[str, Any] = request.get_json(force=True, silent=False)
    result = save_llm_document_review(
        paths,
        doc_key=doc_key,
        status=body.get("status", ""),
        remark=body.get("remark", ""),
        entities=body.get("entities", []),
        relationships=body.get("relationships", []),
    )
    return jsonify({"ok": True, "review": result, "chunk_id": LLM_FULL_DOCUMENT_CHUNK_ID})


@app.get("/api/llm-review-output-file/<doc_key>")
def api_llm_review_output_file(doc_key: str):
    paths = get_paths()
    path = llm_output_path(paths, doc_key)
    if not path.exists():
        load_llm_review_json(paths, doc_key)
    return send_from_directory(path.parent, path.name, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

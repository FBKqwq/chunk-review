# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from parser import DataPaths, build_review_payload, find_documents
from storage import load_review_json, save_chunk_review, output_path

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_SRC_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_SRC_DIR / "dist"
FRONTEND_DIR = FRONTEND_DIST_DIR if FRONTEND_DIST_DIR.exists() else FRONTEND_SRC_DIR
PATHS = DataPaths(BASE_DIR)

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/documents")
def api_documents():
    return jsonify({"documents": find_documents(PATHS)})


@app.get("/api/review-data/<doc_key>")
def api_review_data(doc_key: str):
    payload = build_review_payload(PATHS, doc_key)
    review_file = load_review_json(PATHS, doc_key)
    review_map = review_file.get("review", {})
    extraction_map = review_file.get("extractions", {})
    for ch in payload["chunks"]:
        chunk_id = ch["chunk_id"]
        if chunk_id in extraction_map:
            ch["entities"] = extraction_map[chunk_id].get("entities", ch["entities"])
            ch["relationships"] = extraction_map[chunk_id].get("relationships", ch["relationships"])
        ch["review"] = review_map.get(chunk_id, {"status": "unreviewed", "remark": ""})
    return jsonify(payload)


@app.post("/api/review-data/<doc_key>/<chunk_id>")
def api_save_chunk(doc_key: str, chunk_id: str):
    body: Dict[str, Any] = request.get_json(force=True, silent=False)
    result = save_chunk_review(
        PATHS,
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
    data = load_review_json(PATHS, doc_key)
    return jsonify(data)


@app.get("/api/review-output-file/<doc_key>")
def api_review_output_file(doc_key: str):
    path = output_path(PATHS, doc_key)
    if not path.exists():
        load_review_json(PATHS, doc_key)
    return send_from_directory(path.parent, path.name, as_attachment=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

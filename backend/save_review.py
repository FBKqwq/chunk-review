# -*- coding: utf-8 -*-
"""
命令行结果初始化/导出脚本。
用法：
  python backend/save_review.py --doc "《白塞综合征诊疗规范》"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parser import DataPaths, find_documents
from storage import load_review_json, output_path


def main():
    base_dir = Path(__file__).resolve().parents[1]
    paths = DataPaths(base_dir)
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", default="", help="文档 key，不填默认第一个")
    args = parser.parse_args()

    docs = find_documents(paths)
    if not docs:
        raise SystemExit("未找到可导出的文档。")
    doc_key = args.doc or docs[0]["doc_key"]
    data = load_review_json(paths, doc_key)
    out = output_path(paths, doc_key)
    print(f"复验结果文件：{out}")
    print(json.dumps({"base_info": data.get("base_info"), "chunks": len(data.get("review", {}))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
命令行解析脚本：将 data/input/chunk 与 data/input/kg_json 解析为前端可用的 review payload。
用法：
  python backend/parse_chunks.py --doc "《白塞综合征诊疗规范》"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parser import DataPaths, build_review_payload, find_documents


def main():
    base_dir = Path(__file__).resolve().parents[1]
    paths = DataPaths(base_dir)
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", default="", help="文档 key，例如：《白塞综合征诊疗规范》")
    parser.add_argument("--out", default="", help="输出路径，不填则打印到控制台")
    args = parser.parse_args()

    docs = find_documents(paths)
    if not docs:
        raise SystemExit("未找到 chunk/kg_json 配对文件。")
    doc_key = args.doc or docs[0]["doc_key"]
    payload = build_review_payload(paths, doc_key)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已输出：{out}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

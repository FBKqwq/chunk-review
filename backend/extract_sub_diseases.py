# -*- coding: utf-8 -*-
"""
从 entitybase 目录提取 sub_disease 实体名称，整合为单一 JSON。
用法：
  python backend/extract_sub_diseases.py
  python backend/extract_sub_diseases.py --out data/output/sub_diseases.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from parser import DataPaths, stem_doc_name


def dedupe_names(names: List[str]) -> List[str]:
    """文档内去重：仅合并字符完全相同的名称，保留首次出现顺序。"""
    seen: set[str] = set()
    unique: List[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return unique


def extract_names_from_entitybase(path: Path) -> List[str]:
    names: List[str] = []
    if not path.exists():
        return names
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("entity_type") != "sub_diseases":
                continue
            name = (record.get("name") or "").strip()
            if name:
                names.append(name)
    return dedupe_names(names)


def collect_sub_disease_names(paths: DataPaths) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for path in sorted(paths.entitybase_dir.glob("*.entity_base.jsonl")):
        names = extract_names_from_entitybase(path)
        if not names:
            continue
        result.append(
            {
                "doc_key": stem_doc_name(path),
                "names": names,
            }
        )
    return result


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    paths = DataPaths(base_dir)
    parser = argparse.ArgumentParser(description="从 entitybase 提取 sub_disease 名称")
    parser.add_argument(
        "--out",
        default=str(paths.output_dir / "sub_diseases.json"),
        help="输出 JSON 路径",
    )
    args = parser.parse_args()

    payload = collect_sub_disease_names(paths)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = sum(len(doc["names"]) for doc in payload)
    print(f"已输出：{out_path}")
    print(f"文档数：{len(payload)}，名称合计：{total} 条")


if __name__ == "__main__":
    main()

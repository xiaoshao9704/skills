#!/usr/bin/env python3
"""Merge OpenAPI JSON patches into an existing OpenAPI JSON document.

This v1 tool focuses on deterministic merge for `paths` and `components.schemas`.
Use JSON input/output to avoid non-stdlib dependencies.
"""

from __future__ import annotations

import argparse
import json
import pathlib


def load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base: dict, patch: dict) -> dict:
    for key, value in patch.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge OpenAPI patch JSON into base OpenAPI JSON.")
    parser.add_argument("--base", required=True, help="Base OpenAPI JSON file path")
    parser.add_argument("--patch", required=True, help="Patch JSON file path")
    parser.add_argument("--out", required=True, help="Output JSON file path")
    args = parser.parse_args()

    base_path = pathlib.Path(args.base)
    patch_path = pathlib.Path(args.patch)
    out_path = pathlib.Path(args.out)

    base_doc = load_json(base_path)
    patch_doc = load_json(patch_path)

    merged = deep_merge(base_doc, patch_doc)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "base": str(base_path),
                "patch": str(patch_path),
                "out": str(out_path),
                "merged_keys": sorted(patch_doc.keys()),
                "note": "当前脚本为 JSON 合并模式；如需 YAML，请在外层流程做 YAML<->JSON 转换。",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

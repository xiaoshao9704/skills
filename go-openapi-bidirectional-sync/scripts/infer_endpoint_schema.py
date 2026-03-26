#!/usr/bin/env python3
"""Infer endpoint request/response hints from Go handler source evidence.

This script is intentionally conservative and emits uncertainty notes.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re

FUNC_PATTERN = re.compile(r"^func\s+(?:\(.*\)\s+)?(?P<name>[A-Za-z0-9_]+)\s*\(")
STATUS_PATTERN = re.compile(r"\.(?:Status|WriteHeader)\s*\(\s*(?:http\.)?Status(?P<code>[A-Za-z0-9_]+)")
JSON_BIND_PATTERN = re.compile(r"\.(?:Bind|BindJSON|ShouldBindJSON|Decode)\s*\(")
JSON_WRITE_PATTERN = re.compile(r"\.(?:JSON|Encode)\s*\(")
PATH_PARAM_PATTERN = re.compile(r"(?:URLParam|ChiURLParam|PathValue|\.Param)\s*\(")
QUERY_PATTERN = re.compile(r"(?:Query|URL\.Query\(\)\.Get)\s*\(")
HEADER_PATTERN = re.compile(r"(?:Header\.Get|GetHeader|Request\.Header\.Get)\s*\(")


def find_handler_file(project_root: pathlib.Path, handler_name: str) -> tuple[pathlib.Path | None, int | None]:
    for file in sorted(project_root.rglob("*.go")):
        text = file.read_text(encoding="utf-8", errors="ignore").splitlines()
        for idx, line in enumerate(text, start=1):
            m = FUNC_PATTERN.match(line.strip())
            if m and m.group("name") == handler_name:
                return file, idx
    return None, None


def slice_function_body(lines: list[str], start_line: int) -> list[str]:
    body: list[str] = []
    depth = 0
    started = False

    for line in lines[start_line - 1 :]:
        if "{" in line:
            depth += line.count("{")
            started = True
        if started:
            body.append(line)
        if "}" in line:
            depth -= line.count("}")
            if started and depth <= 0:
                break
    return body


def infer_from_body(body: list[str]) -> dict:
    evidence = {
        "request": {"path_params": False, "query": False, "header": False, "json_body": False},
        "response": {"json": False, "status_codes": []},
        "uncertainties": [],
    }

    status_codes: set[str] = set()
    for line in body:
        s = line.strip()
        if PATH_PARAM_PATTERN.search(s):
            evidence["request"]["path_params"] = True
        if QUERY_PATTERN.search(s):
            evidence["request"]["query"] = True
        if HEADER_PATTERN.search(s):
            evidence["request"]["header"] = True
        if JSON_BIND_PATTERN.search(s):
            evidence["request"]["json_body"] = True
        if JSON_WRITE_PATTERN.search(s):
            evidence["response"]["json"] = True

        status_m = STATUS_PATTERN.search(s)
        if status_m:
            status_codes.add(status_m.group("code"))

    evidence["response"]["status_codes"] = sorted(status_codes)
    if not status_codes:
        evidence["uncertainties"].append("未识别到显式状态码写入，可能依赖框架默认值。")
    if not evidence["response"]["json"]:
        evidence["uncertainties"].append("未识别到显式 JSON 输出调用，响应体结构需要人工确认。")

    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer endpoint schema hints from a Go handler.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--handler", required=True, help="Handler function name, e.g. GetOrder")
    parser.add_argument("--path", required=True, help="Endpoint path for context")
    parser.add_argument("--method", required=True, help="HTTP method for context")
    args = parser.parse_args()

    project_root = pathlib.Path(args.project_root).resolve()
    handler_file, start_line = find_handler_file(project_root, args.handler)

    if not handler_file or not start_line:
        payload = {
            "endpoint": {"path": args.path, "method": args.method.upper()},
            "handler": args.handler,
            "found": False,
            "uncertainties": ["未找到 handler 定义，请确认函数名或项目入口。"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    lines = handler_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    body = slice_function_body(lines, start_line)
    inference = infer_from_body(body)

    payload = {
        "endpoint": {"path": args.path, "method": args.method.upper()},
        "handler": args.handler,
        "found": True,
        "source": {"file": str(handler_file), "line": start_line},
        "inference": inference,
        "note": "该结果为保守推断，请结合业务结构体定义与统一响应封装进一步确认。",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

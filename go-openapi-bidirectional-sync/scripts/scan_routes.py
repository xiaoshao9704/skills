#!/usr/bin/env python3
"""Scan Go router registrations and emit route->handler mappings.

Supports common patterns in chi/gin/echo/net/http projects.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import dataclass, asdict

ROUTE_PATTERNS = [
    # chi explicit method: r.Method("GET", "/x", h)
    re.compile(r"(?P<receiver>\w+)\.Method\s*\(\s*\"(?P<verb>[^\"]+)\"\s*,\s*\"(?P<path>[^\"]+)\"\s*,\s*(?P<handler>[^\),]+)"),
    # chi / net/http style: r.Get("/x", h) / mux.HandleFunc("/x", h)
    re.compile(r"(?P<receiver>\w+)\.(?P<method>Get|Post|Put|Patch|Delete|Options|Head)\s*\(\s*\"(?P<path>[^\"]+)\"\s*,\s*(?P<handler>[^\),]+)"),
    re.compile(r"(?P<receiver>\w+)\.HandleFunc\s*\(\s*\"(?P<path>[^\"]+)\"\s*,\s*(?P<handler>[^\),]+)"),
    # gin / echo style: r.GET("/x", h)
    re.compile(r"(?P<receiver>\w+)\.(?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any)\s*\(\s*\"(?P<path>[^\"]+)\"\s*,\s*(?P<handler>[^\),]+)"),
]

METHOD_NORMALIZE = {
    "GET": "GET",
    "POST": "POST",
    "PUT": "PUT",
    "PATCH": "PATCH",
    "DELETE": "DELETE",
    "OPTIONS": "OPTIONS",
    "HEAD": "HEAD",
    "ANY": "ANY",
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Patch": "PATCH",
    "Delete": "DELETE",
    "Options": "OPTIONS",
    "Head": "HEAD",
    "Method": "METHOD",
}


@dataclass
class RouteRecord:
    method: str
    path: str
    handler: str
    file: str
    line: int
    evidence: str


def iter_go_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.rglob("*.go") if "/vendor/" not in p.as_posix())


def scan_file(path: pathlib.Path) -> list[RouteRecord]:
    routes: list[RouteRecord] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    for idx, line in enumerate(lines, start=1):
        for pattern in ROUTE_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue

            method_raw = match.groupdict().get("verb") or match.groupdict().get("method") or "METHOD"
            routes.append(
                RouteRecord(
                    method=METHOD_NORMALIZE.get(method_raw, method_raw.upper()),
                    path=match.group("path"),
                    handler=match.group("handler").strip(),
                    file=str(path),
                    line=idx,
                    evidence=line.strip(),
                )
            )
            break

    return routes


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Go route registrations.")
    parser.add_argument("--project-root", default=".", help="Go project root path")
    parser.add_argument("--router-file", action="append", default=[], help="Optional specific router file(s)")
    parser.add_argument("--endpoint", help="Optional endpoint filter, exact path match")
    parser.add_argument("--method", help="Optional method filter, e.g. GET")
    args = parser.parse_args()

    root = pathlib.Path(args.project_root).resolve()
    files = [pathlib.Path(p).resolve() for p in args.router_file] if args.router_file else iter_go_files(root)

    all_routes: list[RouteRecord] = []
    for file in files:
        if file.exists() and file.suffix == ".go":
            all_routes.extend(scan_file(file))

    if args.endpoint:
        all_routes = [r for r in all_routes if r.path == args.endpoint]
    if args.method:
        m = args.method.upper()
        all_routes = [r for r in all_routes if r.method == m]

    payload = {
        "project_root": str(root),
        "total_routes": len(all_routes),
        "routes": [asdict(r) for r in all_routes],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import HOME, build_context, ensure_home, list_sources, load_config
from thread_import import import_chatgpt, import_pasted_text, list_chatgpt


def main() -> int:
    parser = argparse.ArgumentParser(description="Ξ Desktop Shell")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("status")

    p = sub.add_parser("import-paste")
    p.add_argument("path", type=Path)
    p.add_argument("--title")

    p = sub.add_parser("list-chatgpt")
    p.add_argument("path", type=Path)

    p = sub.add_parser("import-chatgpt")
    p.add_argument("path", type=Path)
    p.add_argument("--conversation-id", required=True)

    p = sub.add_parser("context")
    p.add_argument("conversation_id")

    args = parser.parse_args()

    if args.cmd == "init":
        ensure_home()
        print(json.dumps({"ok":True, "home":str(HOME)}, indent=2))
    elif args.cmd == "status":
        ensure_home()
        print(json.dumps({
            "home":str(HOME),
            "config":load_config(),
            "sources":list_sources(),
        }, indent=2, ensure_ascii=False))
    elif args.cmd == "import-paste":
        print(json.dumps(import_pasted_text(args.path, args.title), indent=2, ensure_ascii=False))
    elif args.cmd == "list-chatgpt":
        print(json.dumps(list_chatgpt(args.path), indent=2, ensure_ascii=False))
    elif args.cmd == "import-chatgpt":
        print(json.dumps(import_chatgpt(args.path, args.conversation_id), indent=2, ensure_ascii=False))
    elif args.cmd == "context":
        print(json.dumps(build_context(args.conversation_id), indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Ξ.SymbolicCapsuleEngine.v∞
"""
Core symbolic capsule class for recursive, fractal architectures.
Handles capsule creation, stacking, serialization, echo logic, and compression.
"""

from typing import List, Dict, Any
import yaml
import json

class Capsule:
    def __init__(
        self,
        id: str,
        anchor: str,
        mirror: str,
        content: str,
        rules: List[str],
        echo: bool
    ):
        self.id = id
        self.anchor = anchor
        self.mirror = mirror
        self.content = content if isinstance(content, str) else str(content)
        self.rules = rules
        self.echo = echo
        self.children: List['Capsule'] = []

    def add_child(self, capsule: "Capsule") -> None:
        if isinstance(capsule, Capsule):
            self.children.append(capsule)

    def compress(self) -> None:
        if isinstance(self.content, str):
            tokens = self.content.split()
            self.content = ' '.join(sorted(set(tokens), key=tokens.index))
        for child in self.children:
            child.compress()

    def echo_feedback(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "anchor": self.anchor,
            "mirror": self.mirror,
            "status": "echoed",
            "rules": self.rules,
            "child_count": len(self.children),
            "children": [child.echo_feedback() for child in self.children]
        }

    def serialize(self, fmt: str = "yaml") -> Any:
        d = {
            "capsule": {
                "id": self.id,
                "anchor": self.anchor,
                "mirror": self.mirror,
                "content": self.content,
                "rules": self.rules,
                "echo": self.echo,
                "children": [c.serialize(fmt="dict") for c in self.children]
            }
        }
        if fmt == "yaml":
            return yaml.dump(d, sort_keys=False, allow_unicode=True)
        elif fmt == "json":
            return json.dumps(d, indent=2, ensure_ascii=False)
        elif fmt == "dict":
            return d
        elif fmt == "md":
            md = f"## Capsule: {self.id}\n- Anchor: {self.anchor}\n- Mirror: {self.mirror}\n- Content: {self.content}\n- Rules: {self.rules}\n- Echo: {self.echo}\n"
            if self.children:
                md += "\n### Children\n"
                for child in self.children:
                    child_md = child.serialize(fmt="md").replace('\n', '\n    ')
                    md += f"- {child_md}\n"
            return md
        else:
            raise ValueError(f"Unknown format: {fmt}")

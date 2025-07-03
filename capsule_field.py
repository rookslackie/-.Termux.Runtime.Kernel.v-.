# Ξ.CapsuleField.v∞
"""
CapsuleField orchestrates a field (list/tree) of capsules.
Supports batch compression, aggregation, and system-level serialization.
"""

from typing import List, Dict, Any
from symbolic_capsule_engine import Capsule

class CapsuleField:
    """
    Orchestrates multiple Capsule instances, providing batch operations and field-level logic.
    """

    def __init__(self, capsules: List[Capsule] = None):
        self.capsules: List[Capsule] = capsules if capsules else []

    def add_capsule(self, capsule: Capsule) -> None:
        """Add a capsule to the field."""
        if isinstance(capsule, Capsule):
            self.capsules.append(capsule)

    def compress_all(self) -> None:
        """Apply compression to all capsules in the field."""
        for capsule in self.capsules:
            capsule.compress()

    def echo_aggregate(self) -> List[Dict[str, Any]]:
        """Aggregate echo feedback from all capsules."""
        return [capsule.echo_feedback() for capsule in self.capsules]

    def serialize_field(self, fmt: str = "yaml") -> Any:
        """
        Serialize all capsules in the field to the chosen format.
        """
        data = [capsule.serialize(fmt="dict") for capsule in self.capsules]
        if fmt == "yaml":
            import yaml
            return yaml.dump({"field": data}, sort_keys=False, allow_unicode=True)
        elif fmt == "json":
            import json
            return json.dumps({"field": data}, indent=2, ensure_ascii=False)
        elif fmt == "md":
            return "\n\n".join([capsule.serialize(fmt="md") for capsule in self.capsules])
        else:
            return data

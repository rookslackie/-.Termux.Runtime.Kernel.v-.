from symbolic_capsule_engine import Capsule
from capsule_field import CapsuleField
import json

if __name__ == "__main__":
    c1 = Capsule("Ξ.FrameReturn", "⟐", "⊚", "A A B", ["↺", "⋈", "⟐", "⊚"], True)
    c2 = Capsule("Ξ.Sequence", "⟐", "⊚", "B C C", ["⋈", "⟐", "⊚"], True)
    c2.add_child(c1)

    field = CapsuleField([c2])
    field.compress_all()

    echoes = field.echo_aggregate()
    print("# Echo Feedback (field):")
    print(json.dumps(echoes, indent=2, ensure_ascii=False))

    print("\n# YAML Serialization (field):")
    print(field.serialize_field(fmt="yaml"))

    print("\n# Markdown Serialization (field):")
    print(field.serialize_field(fmt="md"))

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic.config import Config
from alembic.script import ScriptDirectory


class MigrationNode:
    def __init__(self, revision: str, down_revision: Optional[str]):
        self.revision = revision
        self.down_revision = down_revision
        self.children: List["MigrationNode"] = []

    def __repr__(self) -> str:
        return f"<MigrationNode {self.revision}>"


class MigrationGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, MigrationNode] = {}

    def add_node(self, revision: str, down_revision: Optional[str]) -> None:
        if revision not in self.nodes:
            self.nodes[revision] = MigrationNode(revision, down_revision)

    def build_links(self) -> None:
        for node in self.nodes.values():
            parent = node.down_revision
            if parent and parent in self.nodes:
                self.nodes[parent].children.append(node)

    def roots(self) -> List[MigrationNode]:
        roots = []
        for node in self.nodes.values():
            if node.down_revision is None:
                roots.append(node)
            elif node.down_revision not in self.nodes:
                roots.append(node)
        return roots

    def heads(self) -> List[MigrationNode]:
        return [n for n in self.nodes.values() if not n.children]

    def detect_orphans(self) -> List[MigrationNode]:
        orphans = []
        for node in self.nodes.values():
            if node.down_revision and node.down_revision not in self.nodes:
                orphans.append(node)
        return orphans

    def print_tree(self, node: MigrationNode, depth: int = 0, visited: Optional[Set[str]] = None) -> None:
        if visited is None:
            visited = set()

        indent = "  " * depth
        print(f"{indent}{node.revision}")

        if node.revision in visited:
            print(f"{indent}  (cycle detected)")
            return

        visited.add(node.revision)

        for child in node.children:
            self.print_tree(child, depth + 1, visited)


def load_graph() -> MigrationGraph:
    alembic_ini = ROOT / "migrations" / "alembic.ini"

    if not alembic_ini.exists():
        raise RuntimeError("Alembic config not found")

    config = Config(str(alembic_ini))
    script = ScriptDirectory.from_config(config)

    graph = MigrationGraph()

    for rev in script.walk_revisions():
        revision = rev.revision
        down_revision = rev.down_revision

        if isinstance(down_revision, tuple):
            down_revision = down_revision[0]

        graph.add_node(revision, down_revision)

    graph.build_links()

    return graph


def print_summary(graph: MigrationGraph) -> None:
    print("\nMigration Summary\n")

    print("Total migrations:", len(graph.nodes))

    roots = graph.roots()
    heads = graph.heads()
    orphans = graph.detect_orphans()

    print("Root migrations:", len(roots))
    for r in roots:
        print("  ", r.revision)

    print("Head migrations:", len(heads))
    for h in heads:
        print("  ", h.revision)

    if len(heads) > 1:
        print("\nWARNING: multiple migration heads detected")

    if orphans:
        print("\nOrphan migrations:")
        for o in orphans:
            print("  ", o.revision, "depends on", o.down_revision)


def main() -> int:
    try:
        graph = load_graph()
    except Exception as exc:
        print("Failed to load migrations:", exc)
        return 2

    print("\nMigration Dependency Graph\n")

    roots = graph.roots()

    if not roots:
        print("No root migration found")
        return 1

    for root in roots:
        graph.print_tree(root)

    print_summary(graph)

    heads = graph.heads()

    if len(heads) > 1:
        print("\nCRITICAL: Multiple migration heads exist.")
        return 1

    print("\nMigration graph is consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Намира всички файлове с име `asgi.py` в директорията на проекта.
Използване:
    python find_asgi.py [път_към_проект]
Ако не е подаден път, се търси в текущата директория.
Изход: пълни пътища до намерените файлове (един на ред).
Връща статус код 0 при намерен(и) файл(ове),
1 ако не е намерен файл, 2 при грешка (напр. невалидна директория).
"""

from __future__ import annotations

import argparse
import os
import sys


def find_asgi(root: str) -> list[str]:
    matches: list[str] = []
    for dirpath, _, files in os.walk(root):
        if "asgi.py" in files:
            matches.append(os.path.join(dirpath, "asgi.py"))
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Намира всички asgi.py файлове в дадена директория."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Път към корена на проекта (по подразбиране: текуща директория)",
    )
    args = parser.parse_args()
    root = os.path.abspath(args.path)

    if not os.path.isdir(root):
        print(f"Грешка: Пътят не е директория: {root}", file=sys.stderr)
        sys.exit(2)

    results = find_asgi(root)
    if not results:
        print("Не е намерен файл asgi.py в посочената директория.", file=sys.stderr)
        sys.exit(1)

    for p in results:
        print(p)

    sys.exit(0)


if __name__ == "__main__":
    main()

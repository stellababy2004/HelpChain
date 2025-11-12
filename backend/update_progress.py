#!/usr/bin/env python3
"""
update_progress.py – Скрипт за автоматично обновяване на прогреса в markdown чеклист

- Брои изпълнените задачи (☑) и общия брой задачи в markdown таблица
- Актуализира лентата за прогрес и процента в отчетния файл

Използване:
    python update_progress.py <път_до_файла>
"""

import re
import sys

PROGRESS_BAR_LENGTH = 20


def count_tasks_and_done(lines):
    total = 0
    done = 0
    for line in lines:
        if re.match(r"\|.*\|.*\|.*\|.*\|.*\|", line):
            if "☑" in line:
                done += 1
                total += 1
            elif "☐" in line:
                total += 1
    return done, total


def update_progress_bar(content, percent):
    filled = int(PROGRESS_BAR_LENGTH * percent // 100)
    empty = PROGRESS_BAR_LENGTH - filled
    bar = "▓" * filled + "░" * empty
    return re.sub(r"Прогрес:.*", f"Прогрес: {bar}  {percent} %", content)


def main():
    if len(sys.argv) < 2:
        print("Използване: python update_progress.py <път_до_файла>")
        sys.exit(1)
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    done, total = count_tasks_and_done(lines)
    percent = int((done / total) * 100) if total else 0
    new_content = update_progress_bar(content, percent)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Обновено: {done}/{total} задачи изпълнени ({percent}%)")


if __name__ == "__main__":
    main()

import os
import subprocess
from datetime import datetime

REPORTS_DIR = "weekly_reports"
TODO_FILE = "todoList"

TEMPLATE = """# Седмичен отчет — {date}

## Какво свършихме тази седмица
{tasks}

## Какво внедрихме
{deploy}

## Какви проблеми решихме
{troubles}

## Как да работиш с новите неща
{howto}

---
*Този отчет е попълнен автоматично и описва с прости думи какво е направено през седмицата.*
"""


def get_git_commits():
    try:
        result = subprocess.run(
            ["git", "log", "--since=7 days ago", "--pretty=format:%s"],
            capture_output=True,
            text=True,
            check=True,
        )
        commits = result.stdout.strip().split("\n")
        return commits
    except Exception:
        return []


def get_todo_tasks():
    tasks = []
    if os.path.exists(TODO_FILE):
        with open(TODO_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("- [x]"):
                    task = line.strip().replace("- [x]", "- ").strip()
                    tasks.append(task)
    return tasks


def summarize(commits, tasks):
    # Прости обобщения
    done = "\n".join(tasks) if tasks else "- Работихме по задачи от проекта."
    deploy = (
        "- Внедрихме нови промени: " + ", ".join(commits[:2])
        if commits
        else "- Няма внедрени промени тази седмица."
    )
    troubles = (
        "- Решихме проблеми, описани в комитите: " + ", ".join(commits[2:4])
        if len(commits) > 2
        else "- Няма големи проблеми тази седмица."
    )
    howto = "- За новите промени виж README или попитай в екипа."
    return done, deploy, troubles, howto


def main():
    today = datetime.today().strftime("%Y-%m-%d")
    filename = f"{today}.md"
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    if os.path.exists(path):
        print(f"Report for {today} already exists: {path}")
        return
    commits = get_git_commits()
    tasks = get_todo_tasks()
    done, deploy, troubles, howto = summarize(commits, tasks)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            TEMPLATE.format(
                date=today, tasks=done, deploy=deploy, troubles=troubles, howto=howto
            )
        )
    print(f"Created weekly report: {path}")


if __name__ == "__main__":
    main()

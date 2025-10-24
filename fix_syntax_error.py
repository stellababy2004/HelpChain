#!/usr/bin/env python3
import re


def fix_syntax_error():
    with open("backend/appy.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find and remove the orphaned line
    # This line appears to be leftover from a ternary operator in sorting logic
    orphaned_line = r't_order == "asc" else Volunteer\.name\.desc\(\)\n'

    if re.search(orphaned_line, content):
        content = re.sub(orphaned_line, "", content)
        print("Found and removed orphaned syntax error line")

        with open("backend/appy.py", "w", encoding="utf-8") as f:
            f.write(content)

        print("Syntax error fixed successfully")
        return True
    else:
        print("Orphaned line not found")
        return False


if __name__ == "__main__":
    fix_syntax_error()

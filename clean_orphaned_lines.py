#!/usr/bin/env python3
import re


def clean_orphaned_sorting_lines():
    with open("backend/appy.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find and remove the orphaned sorting lines that are outside any function
    # These lines appear after the admin_logout function and before the next route
    orphaned_lines_pattern = r'        \)\s*\n\s*elif sort_by == "location":\s*\n\s*query = query\.order_by\(\s*\n\s*Volunteer\.location\.asc\(\)\s*\n\s*if sort_order == "asc"\s*\n\s*else Volunteer\.location\.desc\(\)\s*\n\s*\)\s*\n\s*elif sort_by == "created_at":\s*\n\s*query = query\.order_by\(\s*\n\s*Volunteer\.created_at\.asc\(\)\s*\n\s*if sort_order == "asc"\s*\n\s*else Volunteer\.created_at\.desc\(\)\s*\n\s*\)\s*\n\s*else:\s*\n\s*query = query\.order_by\(Volunteer\.id\.asc\(\)\)\s*\n'

    if re.search(orphaned_lines_pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(
            orphaned_lines_pattern, "", content, flags=re.MULTILINE | re.DOTALL
        )
        print("Found and removed orphaned sorting lines")

        with open("backend/appy.py", "w", encoding="utf-8") as f:
            f.write(content)

        print("Orphaned sorting lines cleaned successfully")
        return True
    else:
        print("Orphaned sorting lines not found")
        return False


if __name__ == "__main__":
    clean_orphaned_sorting_lines()

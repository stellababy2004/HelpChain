#!/usr/bin/env python3
import re


def fix_admin_dashboard():
    with open("backend/appy.py", encoding="utf-8") as f:
        content = f.read()

    # Find the admin_dashboard function and fix the missing closing parenthesis
    # Look for the pattern where return_template ends with current_user=current_user,
    # followed by the next function decorator
    pattern = r'(return render_template\(\s*"admin_dashboard\.html",\s*requests=requests,\s*logs_dict=logs_dict,\s*stats=stats,\s*current_user=current_user,\s*)(?=@app\.route\("/profile")'

    replacement = r"\1)"

    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        print("Fixed missing closing parenthesis in admin_dashboard function")

        with open("backend/appy.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("File updated successfully")
    else:
        print("Pattern not found")


if __name__ == "__main__":
    fix_admin_dashboard()

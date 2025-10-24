lines = []
with open("backend/appy.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the line with 'return render_template' that ends the first admin_dashboard
start_remove = None
for i, line in enumerate(lines):
    if "return render_template(" in line and "admin_dashboard.html" in line:
        # Check if this is followed by orphaned code
        if i + 1 < len(lines) and 'HelpRequest.status == "completed"' in lines[i + 1]:
            start_remove = i + 1
            break

if start_remove is not None:
    # Find the next @app.route decorator
    end_remove = None
    for j in range(start_remove, len(lines)):
        if '@app.route("/admin_dashboard", endpoint="admin_dashboard")' in lines[j]:
            end_remove = j
            break

    if end_remove is not None:
        # Remove the orphaned code
        del lines[start_remove:end_remove]

        # Write back
        with open("backend/appy.py", "w", encoding="utf-8") as f:
            f.writelines(lines)

        print("Removed orphaned code successfully")
    else:
        print("Could not find end marker")
else:
    print("Could not find start marker")

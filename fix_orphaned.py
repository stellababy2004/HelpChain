import re

# Read the file
with open("backend/appy.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the first admin_dashboard function and remove everything after its return until the next @app.route
# Pattern to match: return render_template(...) followed by orphaned code until @app.route("/admin_dashboard"
pattern = r'(return render_template\(\s*"admin_dashboard\.html",\s*requests=requests,\s*logs_dict=logs_dict,\s*stats=stats,\s*current_user=current_user,\s*\)\s*)\s*(\s*HelpRequest\.status == "completed"\s*\)\.count\(\)\s*total_volunteers = Volunteer\.query\.count\(\)\s*except Exception as e:\s*app\.logger\.error\(f"Error fetching dashboard stats: \{e\}"\)\s*total_requests = 0\s*pending_requests = 0\s*completed_requests = 0\s*total_volunteers = 0\s*requests = \{\s*"items": \[\s*\{"id": 1, "name": "Мария", "status": "Активен"\},\s*\{"id": 2, "name": "Георги", "status": "Завършен"\},\s*\]\s*\}\s*logs_dict = \{\s*1: \[\{"status": "Активен", "changed_at": "2025-07-22"\}\],\s*2: \[\{"status": "Завършен", "changed_at": "2025-07-21"\}\],\s*\}\s*stats = \{\s*"total_requests": total_requests,\s*"pending_requests": pending_requests,\s*"completed_requests": completed_requests,\s*"total_volunteers": total_volunteers,\s*\}\s*# Get current admin user for template\s*current_user = None\s*if session\.get\("admin_user_id"\):\s*current_user = db\.session\.get\(AdminUser, session\.get\("admin_user_id"\)\)\s*return render_template\(\s*"admin_dashboard\.html",\s*requests=requests,\s*logs_dict=logs_dict,\s*stats=stats,\s*current_user=current_user,\s*\)\s*)(\s*@app\.route\("/admin_dashboard", endpoint="admin_dashboard"\))'

# Replace with just the return statement and the route decorator
replacement = r"\1\3"

# Apply the replacement
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write back
with open("backend/appy.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Fixed orphaned code removal")

import re

with open("backend/appy.py", encoding="utf-8") as f:
    content = f.read()

# Pattern for the admin_dashboard function
pattern = r'@app\.route\("/api/admin/dashboard", methods=\["GET"\]\)\s*@require_admin_login\s*def api_admin_dashboard\(\):\s*"""API endpoint for admin dashboard data"""\s*try:\s*# Get basic counts\s*volunteers_count = db\.session\.query\(Volunteer\)\.count\(\)\s*requests_count = db\.session\.query\(HelpRequest\)\.count\(\)\s*admins_count = db\.session\.query\(AdminUser\)\.count\(\)\s*# Get recent requests\s*recent_requests = \(\s*db\.session\.query\(HelpRequest\)\.order_by\(HelpRequest\.created_at\.desc\(\)\)\.limit\(5\)\.all\(\)\s*\)\s*requests_data = \[\]\s*for req in recent_requests:\s*requests_data\.append\(\s*\{\s*"id": req\.id,\s*"title": req\.title,\s*"status": req\.status,\s*"created_at": req\.created_at\.isoformat\(\),\s*"requester_name": req\.requester_name,\s*\}\s*\)\s*return jsonify\(\s*\{\s*"stats": \{\s*"volunteers_count": volunteers_count,\s*"requests_count": requests_count,\s*"admins_count": admins_count,\s*\},\s*"recent_requests": requests_data,\s*\}\s*\)\s*except Exception as e:\s*app\.logger\.error\(f"Error getting admin dashboard: \{e\}"\)\s*return jsonify\(\{"error": "Internal server error"\}\), 500'

matches = re.findall(pattern, content, re.DOTALL)

print(f"Found {len(matches)} matches")

if len(matches) > 1:
    # Keep only the first, remove others
    for i in range(1, len(matches)):
        content = content.replace(matches[i], "", 1)

with open("backend/appy.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Duplicates removed")

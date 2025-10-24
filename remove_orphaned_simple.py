#!/usr/bin/env python3
import re


def remove_orphaned_code():
    with open("backend/appy.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the first admin_dashboard function and its return statement
    first_admin_dashboard_pattern = r'(@app\.route\("/admin_dashboard", endpoint="admin_dashboard"\)\s*@require_admin_login\s*def admin_dashboard\(\):\s*.*?return render_template\(\s*"admin_dashboard\.html",\s*requests=requests,\s*logs_dict=logs_dict,\s*stats=stats,\s*current_user=current_user,\s*\)\s*\))'

    # Find the orphaned code that starts with the incomplete query
    orphaned_pattern = r'\s*\)\s*HelpRequest\.status == "completed"\s*\)\.count\(\)\s*total_volunteers = Volunteer\.query\.count\(\)\s*except Exception as e:\s*app\.logger\.error\(f"Error fetching dashboard stats: \{e\}"\)\s*total_requests = 0\s*pending_requests = 0\s*completed_requests = 0\s*total_volunteers = 0\s*requests = \{\s*"items": \[\s*\{"id": 1, "name": "Мария", "status": "Активен"\},\s*\{"id": 2, "name": "Георги", "status": "Завършен"\},\s*\]\s*\}\s*logs_dict = \{\s*1: \[\{"status": "Активен", "changed_at": "2025-07-22"\}\],\s*2: \[\{"status": "Завършен", "changed_at": "2025-07-21"\}\],\s*\}\s*stats = \{\s*"total_requests": total_requests,\s*"pending_requests": pending_requests,\s*"completed_requests": completed_requests,\s*"total_volunteers": total_volunteers,\s*\}\s*# Get current admin user for template\s*current_user = None\s*if session\.get\("admin_user_id"\):\s*current_user = db\.session\.get\(AdminUser, session\.get\("admin_user_id"\)\)\s*return render_template\(\s*"admin_dashboard\.html",\s*requests=requests,\s*logs_dict=logs_dict,\s*stats=stats,\s*current_user=current_user,\s*\)\s*'

    # Find the second admin_dashboard function start
    second_admin_dashboard_pattern = r'(\s*@app\.route\("/admin_dashboard", endpoint="admin_dashboard"\)\s*@require_admin_login\s*def admin_dashboard\(\):)'

    # Combine patterns to find the orphaned code between the first return and second function
    combined_pattern = (
        r"("
        + re.escape("    )\n")
        + r")"
        + orphaned_pattern
        + r'(\s*\n\s*@app\.route\("/admin_dashboard", endpoint="admin_dashboard"\)\s*@require_admin_login\s*def admin_dashboard\(\):)'
    )

    # Try a simpler approach - just remove the orphaned block
    orphaned_block = r'\)\s*HelpRequest\.status == "completed"\s*\)\.count\(\)\s*total_volunteers = Volunteer\.query\.count\(\)\s*except Exception as e:\s*app\.logger\.error\(f"Error fetching dashboard stats: \{e\}"\)\s*total_requests = 0\s*pending_requests = 0\s*completed_requests = 0\s*total_volunteers = 0\s*requests = \{\s*"items": \[\s*\{"id": 1, "name": "Мария", "status": "Активен"\},\s*\{"id": 2, "name": "Георги", "status": "Завършен"\},\s*\]\s*\}\s*logs_dict = \{\s*1: \[\{"status": "Активен", "changed_at": "2025-07-22"\}\],\s*2: \[\{"status": "Завършен", "changed_at": "2025-07-21"\}\],\s*\}\s*stats = \{\s*"total_requests": total_requests,\s*"pending_requests": pending_requests,\s*"completed_requests": completed_requests,\s*"total_volunteers": total_volunteers,\s*\}\s*# Get current admin user for template\s*current_user = None\s*if session\.get\("admin_user_id"\):\s*current_user = db\.session\.get\(AdminUser, session\.get\("admin_user_id"\)\)\s*return render_template\(\s*"admin_dashboard\.html",\s*requests=requests,\s*logs_dict=logs_dict,\s*stats=stats,\s*current_user=current_user,\s*\)\s*'

    # Replace the orphaned code with nothing
    new_content = re.sub(orphaned_block, "", content, flags=re.DOTALL)

    if new_content != content:
        with open("backend/appy.py", "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Orphaned code removed successfully")
        return True
    else:
        print("Could not find orphaned code to remove")
        return False


if __name__ == "__main__":
    remove_orphaned_code()

#!/usr/bin/env python3

# Read the file
with open("backend/appy.py", encoding="utf-8") as f:
    content = f.read()

# Remove the broken code after the first admin_dashboard function
# Find the pattern: return render_template(...) followed by broken code
pattern1 = """    return render_template(
        "admin_dashboard.html",
        requests=requests,
        logs_dict=logs_dict,
        stats=stats,
        current_user=current_user,
    )
            HelpRequest.status == "completed"
        ).count()
        total_volunteers = Volunteer.query.count()
    except Exception as e:
        app.logger.error(f"Error fetching dashboard stats: {e}")
        total_requests = 0
        pending_requests = 0
        completed_requests = 0
        total_volunteers = 0

    requests = {
        "items": [
            {"id": 1, "name": "Мария", "status": "Активен"},
            {"id": 2, "name": "Георги", "status": "Завършен"},
        ]
    }
    logs_dict = {
        1: [{"status": "Активен", "changed_at": "2025-07-22"}],
        2: [{"status": "Завършен", "changed_at": "2025-07-21"}],
    }

    stats = {
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "completed_requests": completed_requests,
        "total_volunteers": total_volunteers,
    }

    # Get current admin user for template
    current_user = None
    if session.get("admin_user_id"):
        current_user = db.session.get(AdminUser, session.get("admin_user_id"))

    return render_template(
        "admin_dashboard.html",
        requests=requests,
        logs_dict=logs_dict,
        stats=stats,
        current_user=current_user,
    )


@app.route("/admin_dashboard", endpoint="admin_dashboard")
@require_admin_login
def admin_dashboard():"""

replacement1 = """    return render_template(
        "admin_dashboard.html",
        requests=requests,
        logs_dict=logs_dict,
        stats=stats,
        current_user=current_user,
    )


@app.route("/profile", methods=["GET", "POST"], endpoint="profile")"""

content = content.replace(pattern1, replacement1)

# Write back
with open("backend/appy.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed duplicated admin_dashboard function")

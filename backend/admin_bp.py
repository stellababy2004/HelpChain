"""
Admin routes for authentication and dashboard
"""

import traceback
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

# Import models explicitly from backend.models module
from backend import models

# Import required modules with absolute paths
# Import db from backend.models to ensure consistency
from extensions import db, mail

AdminUser = models.AdminUser
HelpRequest = models.HelpRequest
Volunteer = models.Volunteer
from permissions import require_admin_login

# Import analytics service for tracking
try:
    from analytics_service import analytics_service
except ImportError:
    analytics_service = None

# Import AI service for chatbot
try:
    from ai_service import ai_service
except ImportError:
    ai_service = None

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def get_db_session():
    """Get the correct database session from current_app extensions"""
    try:
        session_db = current_app.extensions.get("sqlalchemy")
        if session_db:
            return session_db.session
        else:
            # Fallback to global db
            return db.session
    except Exception:
        # Last resort fallback
        return db.session


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    from flask import current_app

    current_app.logger.info("Admin login route called")
    current_app.logger.debug(
        f"Request method: {request.method}, EMAIL_2FA_ENABLED = {current_app.config.get('EMAIL_2FA_ENABLED', False)}"
    )
    # DEBUG: Log current session state
    current_app.logger.info(
        f"admin_login called - session keys: {list(session.keys())}"
    )
    current_app.logger.info(
        f"Current SECRET_KEY: {current_app.config.get('SECRET_KEY', 'NOT_SET')}"
    )
    current_app.logger.info(
        f"Session cookie from request: {request.cookies.get('session', 'NO_COOKIE')}"
    )
    current_app.logger.info(f"Session object id: {id(session)}")
    current_app.logger.info(f"Current directory: {__file__}")
    current_app.logger.info(f"Request form data: {dict(request.form)}")
    error = None
    if request.method == "POST":
        current_app.logger.info("Processing admin login POST request")
        username = request.form.get("username")
        password = request.form.get("password")

        current_app.logger.debug(f"Login attempt for username: {username}")

        try:
            # Get existing admin user (should already exist from app startup)
            # Use get_db_session() to ensure we get the correct db instance
            session_db = get_db_session()
            admin_user = session_db.query(AdminUser).filter_by(username="admin").first()
            if not admin_user:
                current_app.logger.error(
                    "Admin user not found - this should not happen in production"
                )
                error = "Администраторският акаунт не е намерен!"
            else:
                # Check credentials
                if (
                    admin_user
                    and username == admin_user.username
                    and admin_user.check_password(password)
                ):
                    current_app.logger.info(f"Admin login successful for {username}")
                    try:
                        # Check if 2FA is enabled
                        if admin_user.two_factor_enabled:
                            current_app.logger.info(
                                "2FA is enabled, redirecting to 2FA verification"
                            )
                            session["pending_2fa"] = True
                            session["pending_admin_id"] = admin_user.id
                            return redirect(url_for("admin.admin_2fa"))
                        else:
                            current_app.logger.info(
                                "No 2FA required, redirecting to dashboard"
                            )
                            # Clear any volunteer session to prevent conflicts
                            session.pop("volunteer_logged_in", None)
                            session.pop("volunteer_id", None)
                            session.pop("volunteer_name", None)
                            # Set user session
                            session["admin_logged_in"] = True
                            session["admin_user_id"] = admin_user.id
                            session["admin_username"] = admin_user.username
                            session["user_id"] = (
                                admin_user.id
                            )  # For permission system compatibility
                            session.permanent = True  # Make session persistent
                            current_app.logger.info(
                                f"Session set: admin_logged_in={session.get('admin_logged_in')}, admin_user_id={session.get('admin_user_id')}"
                            )
                            # TEMPORARY: Return simple response instead of redirect to test
                            # Track analytics - TEMPORARILY DISABLED
                            # try:
                            #     from analytics_service import analytics_service
                            #     if analytics_service:
                            #         analytics_service.track_event(
                            #             event_type="admin_login",
                            #             event_category="authentication",
                            #             event_action="login_success",
                            #             context={"admin_id": admin_user.id},
                            #         )
                            # except Exception as analytics_error:
                            #     current_app.logger.warning(f"Analytics tracking failed: {analytics_error}")
                            return redirect(url_for("admin.admin_dashboard"))
                    except Exception as session_error:
                        current_app.logger.error(
                            f"Session handling error during login: {session_error}"
                        )
                        db.session.rollback()  # Rollback any pending transactions
                        error = (
                            "Грешка при създаване на сесията. Моля, опитайте отново."
                        )
                else:
                    current_app.logger.warning(
                        f"Failed login attempt for user: {username}, IP: {request.remote_addr}"
                    )
                    error = "Грешно потребителско име или парола!"
                    # Log failed login attempt
                    current_app.logger.warning(
                        f"Failed login attempt for user: {username}, IP: {request.remote_addr}"
                    )
        except Exception as db_error:
            current_app.logger.error(f"Database error during admin login: {db_error}")
            db.session.rollback()  # Ensure database session is clean
            error = "Грешка в базата данни. Моля, опитайте отново по-късно."

    print("DEBUG: Rendering admin_login.html")  # DEBUG
    return render_template("admin_login.html", error=error)


@admin_bp.route("/admin_2fa", methods=["GET", "POST"])
def admin_2fa():
    """Admin 2FA verification page"""
    if not session.get("pending_2fa"):
        return redirect(url_for("admin_login"))

    error = None
    if request.method == "POST":
        token = request.form.get("token", "").strip()

        if not token:
            error = "Моля, въведете TOTP код"
        else:
            admin_user = (
                get_db_session().query(AdminUser).get(session["pending_admin_id"])
            )
            if admin_user and admin_user.verify_totp(token):
                # Clear pending 2FA and set session
                session.pop("pending_2fa", None)
                session.pop("pending_admin_id", None)
                session["admin_logged_in"] = True
                session["admin_user_id"] = admin_user.id
                session["admin_username"] = admin_user.username
                session["user_id"] = admin_user.id
                session.permanent = True

                # Track analytics - SAFE VERSION
                try:
                    from analytics_service import analytics_service

                    if analytics_service:
                        try:
                            analytics_service.track_event(
                                event_type="admin_login",
                                event_category="authentication",
                                event_action="2fa_success",
                                context={"admin_id": admin_user.id},
                            )
                        except Exception:
                            pass  # Silent failure
                except Exception:
                    pass  # Silent failure

                return redirect(url_for("admin.admin_dashboard"))
            else:
                error = "Невалиден TOTP код"

    return render_template("admin_2fa.html", error=error)


@admin_bp.route("/logout", methods=["POST"])
def admin_logout():
    """Admin logout"""
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    session.pop("user_id", None)  # Clear permission system user_id
    flash("Излезе от админ панела.", "info")
    return redirect(url_for("admin_login"))


@admin_bp.route("/dashboard")
@require_admin_login
def admin_dashboard():
    """Admin dashboard"""
    from flask import current_app

    # DEBUG: Log session state
    current_app.logger.info(
        f"admin_dashboard called - session keys: {list(session.keys())}"
    )
    current_app.logger.info(f"admin_logged_in: {session.get('admin_logged_in')}")
    current_app.logger.info(f"admin_user_id: {session.get('admin_user_id')}")
    current_app.logger.info(f"admin_username: {session.get('admin_username')}")
    current_app.logger.info(
        f"Session cookie from request: {request.cookies.get('session', 'NO_COOKIE')}"
    )
    current_app.logger.info(f"Session object id: {id(session)}")
    current_app.logger.info(
        f"Current SECRET_KEY: {current_app.config.get('SECRET_KEY', 'NOT_SET')}"
    )

    # Get filter parameter
    filter_param = request.args.get("filter", "all")

    # Get real statistics from database
    try:
        # Check if HelpRequest model is available
        total_requests = db.session.query(HelpRequest).count()
        pending_requests = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.status == "pending")
            .count()
        )
        completed_requests = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.status == "completed")
            .count()
        )
        total_volunteers = db.session.query(Volunteer).count()
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}")
        total_requests = 0
        pending_requests = 0
        completed_requests = 0
        total_volunteers = 0

    # Get filtered requests based on filter parameter
    try:
        if filter_param == "pending":
            requests_query = db.session.query(HelpRequest).filter(
                HelpRequest.status == "pending"
            )
        elif filter_param == "completed":
            requests_query = db.session.query(HelpRequest).filter(
                HelpRequest.status == "completed"
            )
        else:  # "all" or default
            requests_query = db.session.query(HelpRequest)

        # Limit to recent requests for dashboard display
        requests = (
            requests_query.order_by(HelpRequest.created_at.desc()).limit(10).all()
        )

        # Convert to the expected format for template
        requests_data = []
        for req in requests:
            requests_data.append(
                {
                    "id": req.id,
                    "name": getattr(req, "name", "Неизвестно име"),
                    "status": req.status,
                    "created_at": (
                        req.created_at.strftime("%Y-%m-%d %H:%M")
                        if req.created_at
                        else "Няма дата"
                    ),
                }
            )

        requests = {"items": requests_data}

    except Exception as e:
        current_app.logger.error(f"Error fetching filtered requests: {e}")
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
    try:
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))
    except Exception as e:
        current_app.logger.error(f"Error fetching current admin user: {e}")
        current_user = None

    return render_template(
        "admin_dashboard.html",
        requests=requests,
        logs_dict=logs_dict,
        stats=stats,
        current_user=current_user,
        current_filter=filter_param,
    )


# Request management routes
@admin_bp.route("/request/<int:request_id>/approve", methods=["POST"])
@require_admin_login
def admin_approve_request(request_id):
    """Approve a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request_obj.status != "pending":
            return (
                jsonify({"success": False, "message": "Заявката вече е обработена"}),
                400,
            )

        request_obj.status = "approved"
        db.session.commit()

        # Track analytics - SAFE VERSION
        try:
            from analytics_service import analytics_service

            if analytics_service:
                try:
                    analytics_service.track_event(
                        event_type="request_action",
                        event_category="admin",
                        event_action="approve_request",
                        context={"request_id": request_id},
                    )
                except Exception:
                    pass  # Silent failure
        except Exception:
            pass  # Silent failure

        return jsonify({"success": True, "message": "Заявката е одобрена успешно"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving request {request_id}: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при одобряване на заявката"}),
            500,
        )


@admin_bp.route("/request/<int:request_id>/reject", methods=["POST"])
@require_admin_login
def admin_reject_request(request_id):
    """Reject a help request"""
    try:
        data = request.get_json() or {}
        reason = (data.get("reason") or "").strip()

        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request_obj.status != "pending":
            return (
                jsonify({"success": False, "message": "Заявката вече е обработена"}),
                400,
            )

        request_obj.status = "rejected"
        if reason:
            # Store rejection reason (you might want to add a field to the model)
            request_obj.rejection_reason = reason

        db.session.commit()

        # Track analytics - SAFE VERSION
        try:
            from analytics_service import analytics_service

            if analytics_service:
                try:
                    analytics_service.track_event(
                        event_type="request_action",
                        event_category="admin",
                        event_action="reject_request",
                        context={"request_id": request_id, "reason": reason},
                    )
                except Exception:
                    pass  # Silent failure
        except Exception:
            pass  # Silent failure

        return jsonify({"success": True, "message": "Заявката е отхвърлена успешно"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting request {request_id}: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при отхвърляне на заявката"}),
            500,
        )


@admin_bp.route("/request/<int:request_id>/assign", methods=["POST"])
@require_admin_login
def admin_assign_volunteer(request_id):
    """Assign a volunteer to a help request"""
    try:
        data = request.get_json() or {}
        volunteer_id = data.get("volunteer_id")

        if not volunteer_id:
            return (
                jsonify({"success": False, "message": "Не е посочен доброволец"}),
                400,
            )

        request_obj = db.session.query(HelpRequest).get_or_404(request_id)
        volunteer = db.session.query(Volunteer).get_or_404(volunteer_id)

        if request_obj.status != "approved":
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Заявката трябва да бъде одобрена преди присвояване",
                    }
                ),
                400,
            )

        # Here you would typically create a task from the request
        # For now, just update the request status
        request_obj.status = "assigned"
        request_obj.assigned_volunteer_id = volunteer.id
        db.session.commit()

        # Track analytics - SAFE VERSION
        try:
            from analytics_service import analytics_service

            if analytics_service:
                try:
                    analytics_service.track_event(
                        event_type="request_action",
                        event_category="admin",
                        event_action="assign_volunteer",
                        context={
                            "request_id": request_id,
                            "volunteer_id": volunteer_id,
                        },
                    )
                except Exception:
                    pass  # Silent failure
        except Exception:
            pass  # Silent failure

        return jsonify(
            {
                "success": True,
                "message": f"Доброволецът {volunteer.name} е присвоен успешно",
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error assigning volunteer to request {request_id}: {e}"
        )
        return (
            jsonify(
                {"success": False, "message": "Грешка при присвояване на доброволец"}
            ),
            500,
        )


@admin_bp.route("/request/<int:request_id>/delete", methods=["POST"])
@require_admin_login
def admin_delete_request(request_id):
    """Delete a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        # Optional: Check if request can be deleted (not assigned, etc.)
        if request_obj.status == "assigned":
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Не може да изтриете присвоена заявка",
                    }
                ),
                400,
            )

        db.session.delete(request_obj)
        db.session.commit()

        # Track analytics - SAFE VERSION
        try:
            from analytics_service import analytics_service

            if analytics_service:
                try:
                    analytics_service.track_event(
                        event_type="request_action",
                        event_category="admin",
                        event_action="delete_request",
                        context={"request_id": request_id},
                    )
                except Exception:
                    pass  # Silent failure
        except Exception:
            pass  # Silent failure

        return jsonify({"success": True, "message": "Заявката е изтрита успешно"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting request {request_id}: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при изтриване на заявката"}),
            500,
        )


@admin_bp.route("/request/<int:request_id>/edit", methods=["GET", "POST"])
@require_admin_login
def admin_edit_request(request_id):
    """Edit a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request.method == "POST":
            # Update request fields
            request_obj.name = request.form.get("name", request_obj.name)
            request_obj.email = request.form.get("email", request_obj.email)
            request_obj.message = request.form.get("message", request_obj.message)
            request_obj.title = request.form.get("category", request_obj.title)
            request_obj.location_text = request.form.get(
                "location", request_obj.location_text
            )

            db.session.commit()

            flash("Заявката е обновена успешно!", "success")
            return redirect(
                url_for("admin.admin_request_details", request_id=request_id)
            )

        # Get current admin user
        current_user = None
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))

        return render_template(
            "admin_edit_request.html", request=request_obj, current_user=current_user
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing request {request_id}: {e}")
        flash("Грешка при редактиране на заявката", "error")
        return redirect(url_for("admin.admin_request_details", request_id=request_id))


@admin_bp.route("/request/<int:request_id>")
@require_admin_login
def admin_request_details(request_id):
    """View details of a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        # Get current admin user
        current_user = None
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))

        return render_template(
            "admin_request_details.html", request=request_obj, current_user=current_user
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error viewing request {request_id}: {e}")
        flash("Грешка при зареждане на детайлите на заявката", "error")
        return redirect(url_for("admin.admin_dashboard"))

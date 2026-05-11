
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from backend.appy import app
from backend.extensions import db


DEMO_TAG = "[DEMO ENTERPRISE]"
DEMO_PASSWORD = "Demo123!"


def now():
    return datetime.utcnow()


def iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def local_db_path() -> Path:
    with app.app_context():
        url = str(db.engine.url)

    if not url.startswith("sqlite:///"):
        raise SystemExit(f"Refusing to seed non-SQLite database: {url}")

    raw = url.replace("sqlite:///", "", 1)
    path = Path(raw)

    if not path.exists():
        raise SystemExit(f"SQLite database not found: {path}")

    if "hc_local_dev.db" not in str(path):
        raise SystemExit(f"Refusing to seed unexpected DB path: {path}")

    return path


def columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def insert(conn, table, data):
    cols = columns(conn, table)
    payload = {k: v for k, v in data.items() if k in cols}
    keys = list(payload.keys())
    placeholders = ", ".join(["?"] * len(keys))
    sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [payload[k] for k in keys])
    return cur.lastrowid


def get_or_create_structure(conn, name, slug):
    row = conn.execute("SELECT id FROM structures WHERE slug = ?", (slug,)).fetchone()
    if row:
        sid = row[0]
        conn.execute(
            "UPDATE structures SET name = ?, status = ? WHERE id = ?",
            (name, "active", sid),
        )
        return sid

    return insert(
        conn,
        "structures",
        {
            "name": name,
            "slug": slug,
            "status": "active",
            "created_at": iso(now() - timedelta(days=45)),
        },
    )


def create_service(conn, structure_id, code, name):
    row = conn.execute(
        "SELECT id FROM structure_services WHERE structure_id = ? AND code = ?",
        (structure_id, code),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE structure_services SET name = ?, is_active = 1 WHERE id = ?",
            (name, row[0]),
        )
        return row[0]

    return insert(
        conn,
        "structure_services",
        {
            "structure_id": structure_id,
            "code": code,
            "name": name,
            "is_active": 1,
            "created_at": iso(now() - timedelta(days=40)),
        },
    )


def get_or_create_admin(conn, username, email, role, structure_id=None):
    row = conn.execute("SELECT id FROM admin_users WHERE username = ?", (username,)).fetchone()
    payload = {
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(DEMO_PASSWORD),
        "role": role,
        "is_active": 1,
        "structure_id": structure_id,
        "mfa_enabled": 0,
        "must_change_password": 0,
        "onboarding_step": "complete",
        "onboarding_completed_at": iso(now() - timedelta(days=20)),
    }

    if row:
        admin_id = row[0]
        sets = ", ".join([f"{k}=?" for k in payload.keys()])
        conn.execute(f"UPDATE admin_users SET {sets} WHERE id=?", list(payload.values()) + [admin_id])
        return admin_id

    return insert(conn, "admin_users", payload)


def get_or_create_user(conn, username, email, role, structure_id):
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    payload = {
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(DEMO_PASSWORD),
        "role": role,
        "is_active": 1,
        "structure_id": structure_id,
    }

    if row:
        user_id = row[0]
        sets = ", ".join([f"{k}=?" for k in payload.keys()])
        conn.execute(f"UPDATE users SET {sets} WHERE id=?", list(payload.values()) + [user_id])
        return user_id

    return insert(conn, "users", payload)


def create_intervenant(conn, structure_id, name, actor_type, email, location, lat, lon):
    return insert(
        conn,
        "intervenants",
        {
            "structure_id": structure_id,
            "name": name,
            "actor_type": actor_type,
            "email": email,
            "phone": "+33 1 00 00 00 00",
            "location": location,
            "is_active": 1,
            "created_at": iso(now() - timedelta(days=30)),
            "latitude": lat,
            "longitude": lon,
        },
    )


def create_request(conn, *, structure_id, service_id, user_id, owner_id, assigned_volunteer_id, title, city, category, status, priority, risk_score, risk_level, days_old, hours_since_update, lat, lon):
    created = now() - timedelta(days=days_old)
    updated = now() - timedelta(hours=hours_since_update)

    return insert(
        conn,
        "requests",
        {
            "title": f"{DEMO_TAG} {title}",
            "description": f"Situation pilote creee pour demonstrer le suivi operationnel HelpChain: {title}.",
            "name": "Referent structure",
            "email": "demo-contact@helpchain.local",
            "phone": "+33 1 23 45 67 89",
            "city": city,
            "region": "Ile-de-France",
            "location_text": city,
            "message": "Demande recue via canal terrain, qualification initiale effectuee.",
            "status": status,
            "priority": priority,
            "category": category,
            "source_channel": "demo_enterprise_seed",
            "assigned_volunteer_id": assigned_volunteer_id,
            "created_at": iso(created),
            "updated_at": iso(updated),
            "is_archived": 0,
            "latitude": lat,
            "longitude": lon,
            "structure_id": structure_id,
            "service_id": service_id,
            "user_id": user_id,
            "owner_id": owner_id,
            "owned_at": iso(created + timedelta(hours=2)) if owner_id else None,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_signals": "sla_delay,unassigned,high_vulnerability" if risk_score >= 75 else "normal_followup",
            "risk_last_updated": iso(updated),
            "address_line": "Adresse masquee - demo",
            "postcode": "75000" if city == "Paris" else "92100",
            "country": "France",
            "normalized_address": city + ", France",
            "geocoding_status": "ok",
        },
    )


def create_case(conn, request_id, structure_id, owner_user_id, prof_id, status, priority, risk_score, days_old, hours_since_activity, lat, lon):
    created = now() - timedelta(days=days_old)
    last_activity = now() - timedelta(hours=hours_since_activity)

    return insert(
        conn,
        "cases",
        {
            "request_id": request_id,
            "structure_id": structure_id,
            "owner_user_id": owner_user_id,
            "assigned_professional_lead_id": prof_id,
            "latitude": lat,
            "longitude": lon,
            "status": status,
            "priority": priority,
            "risk_score": risk_score,
            "opened_at": iso(created),
            "assigned_at": iso(created + timedelta(hours=4)) if owner_user_id else None,
            "resolved_at": None,
            "closed_at": None,
            "last_activity_at": iso(last_activity),
            "created_at": iso(created),
            "updated_at": iso(last_activity),
        },
    )


def cleanup(conn):
    request_ids = [r[0] for r in conn.execute("SELECT id FROM requests WHERE title LIKE ?", (DEMO_TAG + "%",)).fetchall()]
    if request_ids:
        q = ",".join(["?"] * len(request_ids))
        case_ids = [r[0] for r in conn.execute(f"SELECT id FROM cases WHERE request_id IN ({q})", request_ids).fetchall()]

        if case_ids:
            cq = ",".join(["?"] * len(case_ids))
            for table in ["case_events", "case_participants", "case_collaborators"]:
                conn.execute(f"DELETE FROM {table} WHERE case_id IN ({cq})", case_ids)

        for table in ["assignments", "request_activities", "request_logs", "request_metrics", "volunteer_actions", "volunteer_interests", "volunteer_request_states"]:
            if table in table_names(conn):
                conn.execute(f"DELETE FROM {table} WHERE request_id IN ({q})", request_ids)

        conn.execute(f"DELETE FROM cases WHERE request_id IN ({q})", request_ids)
        conn.execute(f"DELETE FROM requests WHERE id IN ({q})", request_ids)

    conn.execute("DELETE FROM professional_lead_activities WHERE professional_lead_id IN (SELECT id FROM professional_leads WHERE source = 'enterprise_demo_seed')")
    conn.execute("DELETE FROM professional_leads WHERE source = 'enterprise_demo_seed'")
    conn.execute("DELETE FROM notification_jobs WHERE event_type LIKE 'enterprise_demo_%'")
    conn.execute("DELETE FROM admin_audit_events WHERE action LIKE 'enterprise_demo_%'")
    conn.execute("DELETE FROM intervenants WHERE email LIKE '%@demo.helpchain.local'")


def table_names(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def main():
    db_path = local_db_path()
    print(f"[DEMO SEED] DB: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        cleanup(conn)

        paris_id = get_or_create_structure(conn, "Ville de Paris", "ville-paris")
        boulogne_id = get_or_create_structure(conn, "Ville de Boulogne-Billancourt", "boulogne-billancourt")

        paris_services = {
            "social": create_service(conn, paris_id, "action-sociale", "Action sociale"),
            "housing": create_service(conn, paris_id, "hebergement-urgence", "Hebergement urgence"),
            "seniors": create_service(conn, paris_id, "coordination-seniors", "Coordination seniors"),
            "psy": create_service(conn, paris_id, "cellule-psychologique", "Cellule psychologique"),
            "food": create_service(conn, paris_id, "aide-alimentaire", "Aide alimentaire"),
            "risk": create_service(conn, paris_id, "violence-intrafamiliale", "Violence intrafamiliale"),
        }

        boulogne_services = {
            "ccas": create_service(conn, boulogne_id, "ccas", "CCAS Boulogne"),
            "field": create_service(conn, boulogne_id, "solidarite-terrain", "Solidarite terrain"),
            "family": create_service(conn, boulogne_id, "familles", "Accompagnement familles"),
            "medical": create_service(conn, boulogne_id, "coordination-medicale", "Coordination medicale"),
            "home": create_service(conn, boulogne_id, "intervention-domicile", "Intervention domicile"),
        }

        superadmin = get_or_create_admin(conn, "demo.superadmin", "demo.superadmin@helpchain.local", "superadmin", None)
        paris_admin = get_or_create_admin(conn, "paris.admin", "paris.admin@demo.helpchain.local", "admin", paris_id)
        paris_ops = get_or_create_admin(conn, "paris.ops", "paris.ops@demo.helpchain.local", "ops", paris_id)
        paris_readonly = get_or_create_admin(conn, "paris.superviseur", "paris.superviseur@demo.helpchain.local", "readonly", paris_id)
        boulogne_admin = get_or_create_admin(conn, "boulogne.admin", "boulogne.admin@demo.helpchain.local", "admin", boulogne_id)
        boulogne_ops = get_or_create_admin(conn, "boulogne.ops", "boulogne.ops@demo.helpchain.local", "ops", boulogne_id)

        paris_user = get_or_create_user(conn, "paris.agent", "paris.agent@demo.helpchain.local", "operator", paris_id)
        paris_coord = get_or_create_user(conn, "paris.coord", "paris.coord@demo.helpchain.local", "coordinator", paris_id)
        boulogne_user = get_or_create_user(conn, "boulogne.agent", "boulogne.agent@demo.helpchain.local", "operator", boulogne_id)
        boulogne_coord = get_or_create_user(conn, "boulogne.coord", "boulogne.coord@demo.helpchain.local", "coordinator", boulogne_id)

        intervenants = [
            create_intervenant(conn, paris_id, "Sophie Martin", "social_worker", "sophie.martin@demo.helpchain.local", "Paris 12", 48.846, 2.377),
            create_intervenant(conn, paris_id, "Karim Benali", "field_operator", "karim.benali@demo.helpchain.local", "Paris 18", 48.892, 2.344),
            create_intervenant(conn, paris_id, "Claire Dubois", "psychologist", "claire.dubois@demo.helpchain.local", "Paris 15", 48.841, 2.300),
            create_intervenant(conn, boulogne_id, "Camille Leroy", "ccas_agent", "camille.leroy@demo.helpchain.local", "Boulogne-Billancourt", 48.839, 2.239),
            create_intervenant(conn, boulogne_id, "Nicolas Petit", "home_visit", "nicolas.petit@demo.helpchain.local", "Boulogne-Billancourt", 48.835, 2.245),
            create_intervenant(conn, boulogne_id, "Amina Diallo", "family_support", "amina.diallo@demo.helpchain.local", "Boulogne-Billancourt", 48.842, 2.232),
        ]

        pro_ids = []
        for full_name, city, profession, org, owner in [
            ("Dr Anne Moreau", "Paris", "Psychologue", "Reseau Psy Paris", paris_admin),
            ("Marc Lefevre", "Paris", "Travailleur social", "Association Solidarite 75", paris_admin),
            ("Julie Garnier", "Boulogne-Billancourt", "Infirmiere coordinatrice", "Cabinet Sante Boulogne", boulogne_admin),
            ("Paul Bernard", "Boulogne-Billancourt", "Mediation familiale", "Maison des Familles 92", boulogne_admin),
        ]:
            pid = insert(conn, "professional_leads", {
                "email": full_name.lower().replace(" ", ".") + "@demo-partner.local",
                "full_name": full_name,
                "phone": "+33 6 00 00 00 00",
                "city": city,
                "profession": profession,
                "organization": org,
                "availability": "2-3 demi-journees / semaine",
                "message": "Partenaire pilote disponible pour coordination territoriale.",
                "source": "enterprise_demo_seed",
                "locale": "fr",
                "status": "approved",
                "notes": "Demo enterprise partner",
                "contacted_at": iso(now() - timedelta(days=12)),
                "created_at": iso(now() - timedelta(days=20)),
                "owner_admin_id": owner,
                "last_touched_at": iso(now() - timedelta(days=2)),
                "last_touched_by_admin_id": owner,
                "next_action_at": iso(now() + timedelta(days=3)),
                "next_action_note": "Point de suivi pilote",
            })
            pro_ids.append(pid)

        scenarios = [
            (paris_id, paris_services["food"], paris_user, paris_coord, intervenants[0], "Aide alimentaire urgente - Famille Martin", "Paris", "food", "new", "critical", 92, "critical", 3, 96, 48.8566, 2.3522),
            (paris_id, paris_services["housing"], paris_user, None, None, "Hebergement temporaire - Mere avec enfant", "Paris", "housing", "new", "critical", 88, "critical", 2, 80, 48.864, 2.349),
            (paris_id, paris_services["seniors"], paris_coord, paris_coord, intervenants[1], "Isolement senior - Visite a domicile", "Paris", "seniors", "assigned", "high", 71, "high", 5, 12, 48.892, 2.344),
            (paris_id, paris_services["psy"], paris_user, paris_coord, intervenants[2], "Soutien psychologique - Adolescente", "Paris", "psychological", "in_progress", "high", 68, "high", 4, 7, 48.841, 2.300),
            (paris_id, paris_services["risk"], paris_user, None, None, "Signalement risque familial - Suivi discret", "Paris", "safety", "new", "critical", 95, "critical", 1, 4, 48.853, 2.360),
            (paris_id, paris_services["social"], paris_coord, paris_coord, intervenants[0], "Regularisation administrative - Dossier incomplet", "Paris", "admin", "in_progress", "medium", 44, "medium", 9, 24, 48.870, 2.330),
            (boulogne_id, boulogne_services["ccas"], boulogne_user, boulogne_coord, intervenants[3], "Aide alimentaire - Couple retraite", "Boulogne-Billancourt", "food", "assigned", "high", 65, "high", 3, 18, 48.839, 2.239),
            (boulogne_id, boulogne_services["home"], boulogne_user, boulogne_coord, intervenants[4], "Visite domicile - Perte autonomie", "Boulogne-Billancourt", "home_visit", "in_progress", "medium", 53, "medium", 7, 6, 48.835, 2.245),
            (boulogne_id, boulogne_services["family"], boulogne_coord, None, None, "Accompagnement famille - Rupture de suivi", "Boulogne-Billancourt", "family", "new", "high", 76, "high", 6, 120, 48.842, 2.232),
            (boulogne_id, boulogne_services["medical"], boulogne_user, boulogne_coord, intervenants[5], "Coordination medicale - Sortie hospitalisation", "Boulogne-Billancourt", "medical", "assigned", "high", 69, "high", 2, 9, 48.836, 2.241),
            (boulogne_id, boulogne_services["field"], boulogne_user, boulogne_coord, intervenants[3], "Soutien courses - Personne isolee", "Boulogne-Billancourt", "field", "completed", "low", 25, "low", 12, 2, 48.840, 2.246),
            (boulogne_id, boulogne_services["ccas"], boulogne_coord, boulogne_coord, intervenants[4], "Dossier logement - Pieces manquantes", "Boulogne-Billancourt", "housing", "in_progress", "medium", 39, "medium", 8, 36, 48.838, 2.231),
        ]

        created_requests = []
        created_cases = []

        for idx, s in enumerate(scenarios):
            structure_id, service_id, user_id, owner_id, intervenant_id, title, city, category, status, priority, risk_score, risk_level, days_old, hours_since_update, lat, lon = s
            rid = create_request(
                conn,
                structure_id=structure_id,
                service_id=service_id,
                user_id=user_id,
                owner_id=owner_id,
                assigned_volunteer_id=intervenant_id,
                title=title,
                city=city,
                category=category,
                status=status,
                priority=priority,
                risk_score=risk_score,
                risk_level=risk_level,
                days_old=days_old,
                hours_since_update=hours_since_update,
                lat=lat,
                lon=lon,
            )
            created_requests.append(rid)

            cid = create_case(
                conn,
                rid,
                structure_id,
                owner_id,
                pro_ids[idx % len(pro_ids)] if owner_id else None,
                "active" if status in ("new", "assigned", "in_progress") else "closed",
                priority,
                risk_score,
                days_old,
                hours_since_update,
                lat,
                lon,
            )
            created_cases.append(cid)

            insert(conn, "request_logs", {
                "request_id": rid,
                "action": "Demo request created and qualified",
                "timestamp": iso(now() - timedelta(days=days_old, hours=-1)),
            })

            insert(conn, "request_activities", {
                "request_id": rid,
                "actor_admin_id": paris_admin if structure_id == paris_id else boulogne_admin,
                "action": "status_update",
                "old_value": "new",
                "new_value": status,
                "created_at": iso(now() - timedelta(hours=hours_since_update)),
            })

            insert(conn, "request_metrics", {
                "request_id": rid,
                "time_to_assign": 180 if owner_id else None,
                "time_to_complete": 1440 if status == "completed" else None,
            })

            insert(conn, "case_events", {
                "case_id": cid,
                "actor_user_id": owner_id,
                "event_type": "demo_followup",
                "message": "Point de suivi operationnel ajoute dans le cadre du pilote.",
                "metadata_json": '{"source":"enterprise_demo_seed"}',
                "visibility": "internal",
                "created_at": iso(now() - timedelta(hours=hours_since_update)),
            })

            if intervenant_id:
                insert(conn, "assignments", {
                    "request_id": rid,
                    "intervenant_id": intervenant_id,
                    "structure_id": structure_id,
                    "assigned_by_admin_id": paris_ops if structure_id == paris_id else boulogne_ops,
                    "assigned_at": iso(now() - timedelta(days=days_old - 1)),
                    "status": "active",
                    "notes": "Assignment demo enterprise",
                })

        for n, (recipient, status, attempts, event_type) in enumerate([
            ("paris.ops@demo.helpchain.local", "failed", 2, "enterprise_demo_critical_alert"),
            ("boulogne.ops@demo.helpchain.local", "pending", 1, "enterprise_demo_sla_reminder"),
            ("paris.admin@demo.helpchain.local", "sent", 1, "enterprise_demo_daily_digest"),
        ]):
            insert(conn, "notification_jobs", {
                "channel": "email",
                "event_type": event_type,
                "recipient": recipient,
                "subject": "HelpChain - signal operationnel demo",
                "payload_json": '{"demo": true}',
                "status": status,
                "attempts": attempts,
                "max_attempts": 3,
                "next_retry_at": iso(now() + timedelta(hours=2)) if status != "sent" else None,
                "sent_at": iso(now() - timedelta(hours=1)) if status == "sent" else None,
                "last_error": "SMTP demo unavailable" if status == "failed" else None,
                "structure_id": paris_id if "paris" in recipient else boulogne_id,
                "created_at": iso(now() - timedelta(hours=6 + n)),
                "updated_at": iso(now() - timedelta(hours=1 + n)),
            })

        for action, target_type, target_id, admin_id, username in [
            ("enterprise_demo_seed", "structure", paris_id, superadmin, "demo.superadmin"),
            ("enterprise_demo_case_review", "case", created_cases[0], paris_admin, "paris.admin"),
            ("enterprise_demo_assignment", "request", created_requests[6], boulogne_ops, "boulogne.ops"),
            ("enterprise_demo_sla_review", "request", created_requests[1], paris_ops, "paris.ops"),
        ]:
            insert(conn, "admin_audit_events", {
                "created_at": iso(now() - timedelta(hours=3)),
                "admin_user_id": admin_id,
                "admin_username": username,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "ip": "127.0.0.1",
                "user_agent": "HelpChain enterprise demo seed",
                "payload": '{"demo": true}',
            })

        conn.commit()

        print("\n[DEMO SEED] Enterprise demo data inserted.")
        print(f"Structures: Ville de Paris #{paris_id}, Boulogne-Billancourt #{boulogne_id}")
        print(f"Requests: {len(created_requests)}")
        print(f"Cases: {len(created_cases)}")
        print("Admin demo password:", DEMO_PASSWORD)
        print("Useful logins:")
        print(" - demo.superadmin / Demo123!")
        print(" - paris.admin / Demo123!")
        print(" - paris.ops / Demo123!")
        print(" - boulogne.admin / Demo123!")
        print(" - boulogne.ops / Demo123!")

    finally:
        conn.close()


if __name__ == "__main__":
    main()

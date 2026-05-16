from bs4 import BeautifulSoup


def _add_notification_job(session, *, status: str, attempts: int = 0):
    from backend.models import NotificationJob, Structure, utc_now

    structure = session.query(Structure).filter_by(slug="default").first()
    now = utc_now()
    job = NotificationJob(
        channel="email",
        event_type="pipeline_count_test",
        recipient=f"{status}-{attempts}@test.local",
        subject="Pipeline count test",
        payload_json='{"template":"emails/test.html","context":{},"purpose":"test"}',
        status=status,
        attempts=attempts,
        max_attempts=5,
        next_retry_at=now,
        structure_id=getattr(structure, "id", None),
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    session.commit()
    return job


def _admin_home_pipeline_counts(html: str) -> dict[str, int]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h2", string=lambda text: text and "Pipeline notifications" in text)
    assert heading is not None
    section = heading.find_parent("section")
    assert section is not None

    def value_for_href(fragment: str) -> int:
        link = section.select_one(f'a[href*="{fragment}"]')
        assert link is not None
        return int(link.select_one("strong").get_text(strip=True))

    pending_link = section.select_one('a[href$="/admin/notifications"]')
    assert pending_link is not None
    return {
        "pending": int(pending_link.select_one("strong").get_text(strip=True)),
        "retry": value_for_href("status=retry"),
        "failed": value_for_href("status=failed"),
    }


def _ops_notification_summary_counts(html: str) -> dict[str, int]:
    soup = BeautifulSoup(html, "html.parser")
    values = [
        int(node.get_text(strip=True))
        for node in soup.select(".hc-notify-summary__value")[:3]
    ]
    assert len(values) == 3
    return {"pending": values[0], "retry": values[1], "failed": values[2]}


def test_admin_home_pipeline_notifications_use_notification_jobs(
    authenticated_admin_client, session
):
    _add_notification_job(session, status="pending", attempts=0)
    _add_notification_job(session, status="retry", attempts=1)
    _add_notification_job(session, status="pending", attempts=1)
    _add_notification_job(session, status="failed", attempts=5)

    response = authenticated_admin_client.get("/admin/home")

    assert response.status_code == 200
    assert _admin_home_pipeline_counts(response.get_data(as_text=True)) == {
        "pending": 1,
        "retry": 2,
        "failed": 1,
    }


def test_ops_notifications_summary_uses_same_pipeline_buckets(
    authenticated_admin_client, session
):
    _add_notification_job(session, status="pending", attempts=0)
    _add_notification_job(session, status="retry", attempts=1)
    _add_notification_job(session, status="pending", attempts=1)
    _add_notification_job(session, status="dead_letter", attempts=5)

    response = authenticated_admin_client.get("/ops/notifications")

    assert response.status_code == 200
    assert _ops_notification_summary_counts(response.get_data(as_text=True)) == {
        "pending": 1,
        "retry": 2,
        "failed": 1,
    }

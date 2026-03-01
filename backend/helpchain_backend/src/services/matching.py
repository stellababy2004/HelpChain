from ..models import Request


def score_request_for_volunteer(volunteer, request):
    score = 0

    # City match
    if volunteer.location and request.city:
        if volunteer.location.lower() in request.city.lower():
            score += 2

    # Skills match
    if volunteer.skills:
        skills = [s.strip().lower() for s in volunteer.skills.split(",") if s.strip()]

        for skill in skills:
            if request.title and skill in request.title.lower():
                score += 1
            if request.description and skill in request.description.lower():
                score += 1
            if request.category and skill in request.category.lower():
                score += 1

    return score


def get_matched_requests(volunteer, limit=6):
    all_requests = (
        Request.query.filter(Request.deleted_at.is_(None))
        .filter(Request.is_archived.is_(False))
        .all()
    )

    scored = []

    for req in all_requests:
        score = score_request_for_volunteer(volunteer, req)
        if score >= 2:
            scored.append((req, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    return [r[0] for r in scored[:limit]]

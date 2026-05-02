from backend.models_with_analytics import AnalyticsEvent

def compute_radar_v2(session_id):
    events = (
        AnalyticsEvent.query
        .filter_by(user_session=session_id)
        .order_by(AnalyticsEvent.created_at.asc())
        .all()
    )

    if not events:
        return None

    pages = [e.page_url or "" for e in events]
    ref = next((e.referrer for e in events if e.referrer), None)

    score = 0

    # 🎯 Intent scoring
    for p in pages:
        if "/offre" in p:
            score += 30
        elif "/deploiement" in p:
            score += 25
        elif "/professionnels" in p:
            score += 20
        elif "/demander-acces" in p:
            score += 50

    # 🔁 Repeat visits boost
    if len(pages) >= 3:
        score += 15

    # 📡 Source detection
    source = "Direct"
    if ref:
        r = ref.lower()
        if "google" in r:
            source = "Google"
            score += 10
        elif "linkedin" in r:
            source = "LinkedIn"
            score += 15
        elif "chat" in r:
            source = "ChatGPT"
            score += 5

    # 🔥 Temperature
    if score >= 80:
        temperature = "Très chaud"
    elif score >= 50:
        temperature = "Chaud"
    else:
        temperature = "Froid"

    # 💰 Tier
    if score >= 80:
        tier = "A"
    elif score >= 50:
        tier = "B"
    else:
        tier = "C"

    # ⚡ Action
    if tier == "A":
        action = "call_now"
    elif tier == "B":
        action = "send_demo"
    else:
        action = "wait"

    return {
        "score": score,
        "temperature": temperature,
        "tier": tier,
        "source": source,
        "pages_viewed": pages,
        "recommended_action": action,
    }

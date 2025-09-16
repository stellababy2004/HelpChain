# python
# filepath: backend/test_ask.py


def post_and_get(client, payload):
    resp = client.post("/ask", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "answer" in data
    return data["answer"].lower()


def test_ask_returns_english_answer_for_volunteer_keyword(client):
    answer = post_and_get(
        client, {"message": "How to become a volunteer?", "lang": "en"}
    )
    assert "volunteer" in answer or "to become a volunteer" in answer


def test_ask_returns_french_answer_for_benevole_keyword(client):
    answer = post_and_get(client, {"message": "Je veux être bénévole", "lang": "fr"})
    assert (
        "bénévole" in answer
        or "bénévole" in answer.lower()
        or "pour devenir bénévole" in answer
    )


def test_ask_returns_bulgarian_answer_by_default(client):
    answer = post_and_get(client, {"message": "Как да стана доброволец?", "lang": "bg"})
    assert (
        "доброволец" in answer
        or "доброволец" in answer.lower()
        or "попълни формата" in answer
    )


def test_ask_handles_empty_message_and_returns_default_text(client):
    answer = post_and_get(client, {"message": "", "lang": "en"})
    # default assistant reply includes "HelpChain Assistant" in the codebase
    assert "helpchain assistant" in answer or "i can help" in answer

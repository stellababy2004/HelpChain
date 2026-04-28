from backend.helpchain_backend.src.services.import_service import (
    IMPORTABLE_FIELDS,
    IMPORT_ROW_STATUS_REJECTED,
    IMPORT_ROW_STATUS_VALID,
    IMPORT_ROW_STATUS_WARNING,
    build_preview,
    import_batch_source,
    infer_mapping,
    normalize_import_row,
    parse_csv_bytes,
)


def test_parse_csv_and_auto_map_french_headers():
    raw = (
        "Nom;Courriel;Téléphone;Ville;Fonction;Organisation;Disponibilité;Message\n"
        "Claire Martin;claire@example.org;0600000000;Paris;Coordinatrice;CCAS;Matin;Bonjour\n"
    ).encode("utf-8")

    parsed = parse_csv_bytes(raw)

    assert parsed.headers == [
        "Nom",
        "Courriel",
        "Téléphone",
        "Ville",
        "Fonction",
        "Organisation",
        "Disponibilité",
        "Message",
    ]
    mapping = infer_mapping(parsed.headers)
    assert mapping["Nom"] == "full_name"
    assert mapping["Courriel"] == "email"
    assert mapping["Téléphone"] == "phone"
    assert mapping["Ville"] == "city"
    assert mapping["Fonction"] == "profession"


def test_sentence_like_full_name_is_rejected():
    mapping = {
        "Nom": "full_name",
        "Email": "email",
        "Organisation": "organization",
        "Fonction": "profession",
    }
    row = {
        "Nom": "9. IMPACT (1 min)",
        "Email": "impact@example.org",
        "Organisation": "CCAS",
        "Fonction": "Coordination",
    }

    result = normalize_import_row(
        row,
        mapping=mapping,
        batch_id=12,
        row_number=1,
        known_emails=set(),
    )

    assert result.status == IMPORT_ROW_STATUS_REJECTED
    assert "sentence_like_name" in result.reason_codes


def test_paragraph_like_row_is_rejected_for_insufficient_identity():
    mapping = {
        "Nom": "full_name",
        "Ville": "city",
        "Message": "message",
    }
    row = {
        "Nom": "de reduire les erreurs",
        "Ville": "",
        "Message": "Cela permet un vrai pilotage operationnel.",
    }

    result = normalize_import_row(
        row,
        mapping=mapping,
        batch_id=12,
        row_number=2,
        known_emails=set(),
    )

    assert result.status == IMPORT_ROW_STATUS_REJECTED
    assert "missing_contact_identity" in result.reason_codes


def test_missing_email_with_insufficient_fields_is_rejected():
    mapping = {
        "Nom": "full_name",
        "Ville": "city",
    }
    row = {
        "Nom": "Concretement",
        "Ville": "",
    }

    result = normalize_import_row(
        row,
        mapping=mapping,
        batch_id=42,
        row_number=1,
        known_emails=set(),
    )

    assert result.status == IMPORT_ROW_STATUS_REJECTED
    assert "insufficient_fields_for_synthetic_email" in result.reason_codes


def test_missing_email_with_enough_fields_gets_synthetic_email():
    mapping = {
        "Nom": "full_name",
        "Ville": "city",
        "Fonction": "profession",
    }
    row = {
        "Nom": "Claire Martin",
        "Ville": "Paris",
        "Fonction": "Coordinatrice",
    }

    result = normalize_import_row(
        row,
        mapping=mapping,
        batch_id=42,
        row_number=1,
        known_emails=set(),
    )

    assert set(result.payload.keys()) == set(IMPORTABLE_FIELDS)
    assert result.payload["email"].startswith("no-email+")
    assert result.status == IMPORT_ROW_STATUS_WARNING
    assert result.is_valid is True


def test_duplicate_email_is_rejected():
    mapping = {
        "Nom": "full_name",
        "Email": "email",
        "Fonction": "profession",
        "Organisation": "organization",
    }
    row = {
        "Nom": "Jean Dupont",
        "Email": "jean@example.org",
        "Fonction": "Travailleur social",
        "Organisation": "CDAS",
    }

    result = normalize_import_row(
        row,
        mapping=mapping,
        batch_id=42,
        row_number=3,
        known_emails={"jean@example.org"},
    )

    assert result.status == IMPORT_ROW_STATUS_REJECTED
    assert "duplicate_email" in result.reason_codes


def test_preview_counts_warning_and_rejection_reasons():
    raw = (
        "Nom,Email,Ville,Fonction,Organisation\n"
        "Claire Martin,,Paris,Coordinatrice,CCAS\n"
        "Jean Dupont,jean@example.org,Lyon,Travailleur social,CDAS\n"
        "9. IMPACT (1 min),impact@example.org,Paris,Coordination,CCAS\n"
        "Jean Dupont,jean@example.org,Lyon,Travailleur social,CDAS\n"
    ).encode("utf-8")
    parsed = parse_csv_bytes(raw)
    mapping = infer_mapping(parsed.headers)

    preview = build_preview(
        parsed,
        mapping=mapping,
        existing_emails=set(),
        batch_id=42,
    )

    assert preview.valid_rows == 1
    assert preview.warning_rows == 1
    assert preview.rejected_rows == 2
    assert preview.duplicate_rows == 1
    assert preview.rejection_reasons


def test_import_batch_source_scopes_manual_rollback_to_one_batch():
    rows = [
        {"source": import_batch_source(7), "id": 1},
        {"source": import_batch_source(8), "id": 2},
        {"source": "professionnels/pilote", "id": 3},
    ]

    remaining = [row for row in rows if row["source"] != import_batch_source(7)]

    assert [row["id"] for row in remaining] == [2, 3]
    assert all(row["source"] != import_batch_source(7) for row in remaining)

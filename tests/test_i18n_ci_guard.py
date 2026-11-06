from scripts.i18n_ci_guard import (
    AddedLine,
    detect_hardcoded_in_template_lines,
    missing_new_msgids,
)


def test_new_msgid_with_fr_en_bg_passes():
    msgid = "New public heading"
    catalogs = {"FR": {msgid}, "EN": {msgid}, "BG": {msgid}}

    assert missing_new_msgids({msgid: [("templates/index.html", 10)]}, catalogs) == {}


def test_new_msgid_without_bg_fails():
    msgid = "New public heading"
    catalogs = {"FR": {msgid}, "EN": {msgid}, "BG": set()}

    assert "New public heading" in {item[0] for item in missing_new_msgids(
        {msgid: [("templates/index.html", 10)]}, catalogs
    )["BG"]}


def test_new_msgid_without_en_fails():
    msgid = "New public heading"
    catalogs = {"FR": {msgid}, "EN": set(), "BG": {msgid}}

    assert "New public heading" in {item[0] for item in missing_new_msgids(
        {msgid: [("templates/index.html", 10)]}, catalogs
    )["EN"]}


def test_new_visible_public_text_outside_i18n_fails():
    source = '<h1>New visible public text</h1>\n'
    added = [AddedLine("templates/index.html", 1, source)]
    assert detect_hardcoded_in_template_lines(added, source)

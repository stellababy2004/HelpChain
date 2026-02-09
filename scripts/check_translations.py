import gettext

msgs = [
    "All statuses",
    "Filter",
    "Home",
    "Export CSV",
    "Export CSV (anonymized)",
    "⚠️ This export contains personal data.\nInternal use only.\n\nAre you sure you want to continue?",
    "Pending",
    "In progress",
    "Completed",
    "No owner",
    "Stale",
    "No results.",
    "Details",
    "Title",
    "Name",
    "Priority",
    "Category",
    "Created",
    "Closed",
]
for lang in ("bg", "fr"):
    try:
        t = gettext.translation("messages", localedir="translations", languages=[lang])
        _ = t.gettext
    except Exception as e:
        print(f"{lang}: translation load failed: {e}")
        continue
    print(f"--- {lang} ---")
    for m in msgs:
        print(m, "->", _(m))

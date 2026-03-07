#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
from pathlib import Path

from babel.messages import pofile

# Preserve format placeholders and template tokens.
PLACEHOLDER_RE = re.compile(
    r"(\{\{[^{}]+\}\}"  # Jinja placeholders
    r"|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf named
    r"|%[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf positional
    r"|\{[a-zA-Z0-9_:.!-]+\})"  # brace placeholders
)

# Pragmatic high-frequency UI mappings (EN -> FR).
EXACT_MAP = {
    "Access denied.": "Accès refusé.",
    "Active": "Actif",
    "Apply": "Appliquer",
    "Back": "Retour",
    "Back to home": "Retour à l'accueil",
    "Back to list": "Retour à la liste",
    "Back to requests": "Retour aux demandes",
    "Back to site": "Retour au site",
    "Cancel": "Annuler",
    "Category": "Catégorie",
    "Chat": "Discussion",
    "Closed": "Clôturé",
    "Code (6 digits)": "Code (6 chiffres)",
    "Confirm": "Confirmer",
    "Created": "Créé le",
    "Create": "Créer",
    "Dashboard": "Tableau de bord",
    "Description": "Description",
    "Edit": "Modifier",
    "Filter": "Filtrer",
    "Help request": "Demande d'aide",
    "Home": "Accueil",
    "Information:": "Information :",
    "Invalid code.": "Code invalide.",
    "Invalid status.": "Statut invalide.",
    "Invalid user.": "Utilisateur invalide.",
    "Location": "Localisation",
    "Logout": "Déconnexion",
    "Name": "Nom",
    "Need type": "Type de besoin",
    "New request": "Nouvelle demande",
    "No requests.": "Aucune demande.",
    "Open": "Ouvrir",
    "Operations": "Opérations",
    "Page not found.": "Page non trouvée.",
    "Password": "Mot de passe",
    "Priority": "Priorité",
    "Reports": "Rapports",
    "Request": "Demande",
    "Request details": "Détails de la demande",
    "Request preview": "Aperçu de la demande",
    "Requests": "Demandes",
    "Resolved": "Résolu",
    "Save": "Enregistrer",
    "Search": "Rechercher",
    "Settings": "Paramètres",
    "Sign in": "Se connecter",
    "Status": "Statut",
    "Submit": "Soumettre",
    "Submit request": "Soumettre la demande",
    "Success": "Succès",
    "Type": "Type",
    "Unauthorized": "Non autorisé",
    "Unassigned": "Non assigné",
    "Urgency": "Urgence",
    "Urgent": "Urgent",
    "User": "Utilisateur",
    "Username": "Nom d'utilisateur",
    "Verification code": "Code de vérification",
    "Video chat": "Chat vidéo",
    "View requests": "Voir les demandes",
    "Volunteer": "Bénévole",
    "Welcome": "Bienvenue",
}

# Ordered phrase substitutions for longer strings.
PHRASE_MAP = [
    ("Request", "Demande"),
    ("request", "demande"),
    ("Volunteer", "Bénévole"),
    ("volunteer", "bénévole"),
    ("Dashboard", "Tableau de bord"),
    ("dashboard", "tableau de bord"),
    ("Status", "Statut"),
    ("status", "statut"),
    ("Assigned", "Assigné"),
    ("assigned", "assigné"),
    ("Location", "Localisation"),
    ("location", "localisation"),
    ("Created at", "Créé le"),
    ("Created", "Créé"),
    ("Apply filters", "Appliquer les filtres"),
    ("No changes.", "Aucun changement."),
    ("Internal note added.", "Note interne ajoutée."),
    ("Session expired.", "Session expirée."),
    ("Please", "Veuillez"),
    ("Invalid", "Invalide"),
]

FRENCH_HINT_RE = re.compile(
    r"[àâçéèêëîïôûùüÿœ]|"
    r"\b(le|la|les|des|du|de|un|une|et|ou|pour|avec|sur|dans|entre|vous|nous)\b",
    re.IGNORECASE,
)
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Autofill missing fr msgstr values in messages.po")
    ap.add_argument("--po", default="translations/fr/LC_MESSAGES/messages.po")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def mask_placeholders(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def repl(m: re.Match[str]) -> str:
        idx = len(found)
        found.append(m.group(0))
        return f"__HC_PH_{idx}__"

    return PLACEHOLDER_RE.sub(repl, text), found


def unmask_placeholders(text: str, found: list[str]) -> str:
    out = text
    for i, ph in enumerate(found):
        out = out.replace(f"__HC_PH_{i}__", ph)
    return out


def normalize_quotes(text: str) -> str:
    return text.replace("'", "’")


def translate_fallback(msgid: str) -> str:
    src = (msgid or "").strip()
    if not src:
        return ""
    # Already French: keep as canonical FR.
    if FRENCH_HINT_RE.search(src):
        return src
    # No safe offline translator for Cyrillic here: keep source as last resort.
    if CYRILLIC_RE.search(src):
        return src
    if src in EXACT_MAP:
        return EXACT_MAP[src]

    masked, placeholders = mask_placeholders(src)
    out = masked
    for en, fr in PHRASE_MAP:
        out = out.replace(en, fr)

    # Lightweight punctuation typography for FR.
    out = re.sub(r"\s*:\s*", " : ", out)
    out = re.sub(r"\s*;\s*", " ; ", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = normalize_quotes(out)
    out = unmask_placeholders(out, placeholders)
    return out


def main() -> int:
    args = parse_args()
    po_path = Path(args.po)
    if not po_path.exists():
        raise SystemExit(f"PO not found: {po_path}")

    with po_path.open("r", encoding="utf-8") as f:
        catalog = pofile.read_po(f, locale="fr")

    scanned = 0
    filled = 0
    changed_keys: list[str] = []
    for msg in catalog:
        if not msg.id or msg.id == "" or getattr(msg, "obsolete", False):
            continue
        scanned += 1
        if isinstance(msg.string, str) and msg.string.strip():
            continue
        if not isinstance(msg.id, str):
            # plural form: fill singular/plural identically as safe fallback
            base = str(msg.id[0]) if len(msg.id) else ""
            tr = translate_fallback(base)
            if isinstance(msg.string, dict):
                for k in list(msg.string.keys()):
                    msg.string[k] = tr
            else:
                msg.string = tr
            filled += 1
            changed_keys.append(base)
            continue

        tr = translate_fallback(msg.id)
        if tr:
            msg.string = tr
            filled += 1
            changed_keys.append(msg.id)

    if not args.dry_run:
        with po_path.open("wb") as f:
            pofile.write_po(f, catalog, width=120)

    print(f"[fr-autofill] scanned={scanned} filled={filled} dry_run={args.dry_run}")
    if changed_keys:
        preview = changed_keys[:120]
        report = Path("reports/fr_autofill_new_keys.txt")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("\n".join(preview) + "\n", encoding="utf-8")
        print(f"[fr-autofill] wrote preview list: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


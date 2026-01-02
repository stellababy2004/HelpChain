from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Mapping

try:
    from flask_babel import lazy_gettext as _  # type: ignore
except Exception:  # pragma: no cover
    _ = lambda s: s  # noqa: E731


@dataclass(frozen=True)
class CopyPack:
    common: Dict[str, Any]
    request: Dict[str, Any]
    categories: Dict[str, Any]
    _lang: str = "bg"


def _deep_merge_fallback(primary: Any, fallback: Any) -> Any:
    """
    Merge dict-like structures.
    If a key is missing in primary, take it from fallback.
    Primary wins.
    """
    if isinstance(primary, dict) and isinstance(fallback, dict):
        merged = dict(fallback)
        for k, v in primary.items():
            merged[k] = _deep_merge_fallback(v, fallback.get(k))
        return merged
    return primary if primary is not None else fallback


COPY_BG = CopyPack(
    common={
        "back_home": "Към началото",
        "site_name": _("HelpChain"),
        "cta_submit": _("Изпрати"),
        "cta_continue": _("Продължи"),
        "cta_back": _("Назад"),
        "cta_close": _("Затвори"),
        "loading": _("Зареждане…"),
        "required_hint": _("Полета с * са задължителни."),
        "generic_error": _("Нещо се обърка. Опитай отново след малко."),
        "validation_error": _("Провери маркираните полета и опитай отново."),
    },
    request={
        "page_title": _("Подай заявка за помощ"),
        "intro": _("Избери категория и попълни кратко описание. Ако случаят е спешен, отбележи това ясно."),
        "category_label": _("Категория"),
        "category_placeholder": _("Избери категория…"),
        "details_label": _("Описание на ситуацията"),
        "details_help": _("Напиши накратко какво се случва и от какво имаш нужда."),
        "contact_label": _("Контакт за връзка"),
        "contact_help": _("Телефон или имейл, за да можем да се свържем."),
        "location_label": _("Локация"),
        "location_help": _("Град/квартал (без точен адрес на този етап)."),
        "consent_label": _("Съгласен/на съм данните да се използват само за обработка на заявката."),
        "consent_help": _("Не споделяй чувствителни данни, които не са нужни."),
        "emergency_badge": _("СПЕШНО"),
        "emergency_hint": _("Ако има непосредствен риск за живот/здраве, звънни на 112."),
        "emergency_banner_title": _("Спешен случай"),
        "emergency_banner_body": _(
            "Ако има непосредствена опасност, обади се на 112. "
            "HelpChain не е спешна служба, но ще обработим заявката приоритетно."
        ),
        "success_title": _("Заявката е изпратена"),
        "success_body": _("Получихме заявката ти. Ще се свържем при първа възможност."),
        "success_next": _("Можеш да подадеш нова заявка или да се върнеш към началото."),
        "errors": {
            "too_many_requests_title": "Твърде много заявки",
            "too_many_requests_body": "Моля, изчакай малко и опитай отново. Системата те пази от spam и flood.",
            "missing_category": _("Моля, избери категория."),
            "invalid_category": _("Невалидна категория. Избери от списъка."),
            "missing_details": _("Моля, опиши накратко ситуацията."),
            "details_too_short": _("Описанието е твърде кратко. Добави още малко контекст."),
            "missing_contact": _("Моля, остави контакт за връзка."),
            "invalid_contact": _("Контактът изглежда невалиден. Провери телефон/имейл."),
            "missing_consent": _("Трябва да потвърдиш съгласието, за да изпратиш заявката."),
            "rate_limited": _("Твърде много опити за кратко време. Опитай отново след малко."),
        },
    },
    categories={
        "food": {"title": _("Храна"), "hint": _("Нужда от хранителни продукти, доставка или подкрепа за изхранване.")},
        "emergency": {
            "title": _("Спешно"),
            "hint": _("Непосредствен риск или ситуация, изискваща бърза реакция."),
            "is_emergency": True,
            "hotline": _("112"),
            "hotline_hint": _("При непосредствен риск звънни на 112."),
        },
        "medical": {"title": _("Медицинска помощ"), "hint": _("Навигация към услуги, придружаване, административна помощ.")},
        "legal": {"title": _("Правна помощ"), "hint": _("Насоки, документи, консултация, институции.")},
        "shelter": {"title": _("Подслон"), "hint": _("Временно настаняване, кризисен център, базова подкрепа.")},
        "education": {"title": _("Образование"), "hint": _("Записване, подкрепа за ученици/студенти, документи.")},
        "psychological": {"title": _("Психологическа подкрепа"), "hint": _("Подкрепа при стрес, тревожност, кризисни ситуации.")},
        "social": {"title": _("Социална помощ"), "hint": _("Социални услуги, помощи, придружаване, административни въпроси.")},
        "elderly": {"title": _("Подкрепа за възрастни"), "hint": _("Грижа, пазаруване, придружаване, услуги.")},
        "disability": {"title": _("Хора с увреждания"), "hint": _("Достъпност, услуги, документи, помощни средства.")},
    },
    ,
    _lang="bg"
)

COPY_FR = CopyPack(
    common={
        "back_home": "Retour à l’accueil",
        "site_name": _("HelpChain"),
        "cta_submit": _("Envoyer"),
        "cta_continue": _("Continuer"),
        "cta_back": _("Retour"),
        "cta_close": _("Fermer"),
        "loading": _("Chargement…"),
        "required_hint": _("Les champs avec * sont obligatoires."),
        "generic_error": _("Une erreur s’est produite. Réessaie dans un instant."),
        "validation_error": _("Vérifie les champs signalés et réessaie."),
    },
    request={
        "page_title": _("Soumettre une demande d’aide"),
        "intro": _("Choisis une catégorie et décris brièvement la situation. Si c’est urgent, indique-le clairement."),
        "category_label": _("Catégorie"),
        "category_placeholder": _("Choisir une catégorie…"),
        "details_label": _("Description de la situation"),
        "details_help": _("Explique en quelques mots ce qui se passe et ce dont tu as besoin."),
        "contact_label": _("Contact"),
        "contact_help": _("Téléphone ou e-mail afin que nous puissions te recontacter."),
        "location_label": _("Localisation"),
        "location_help": _("Ville/quartier (sans adresse exacte à ce stade)."),
        "consent_label": _("J’accepte que mes données soient utilisées uniquement pour traiter cette demande."),
        "consent_help": _("Ne partage pas de données sensibles inutiles."),
        "emergency_badge": _("URGENT"),
        "emergency_hint": _("En cas de danger immédiat pour la vie/la santé, appelle le 112."),
        "emergency_banner_title": _("Situation urgente"),
        "emergency_banner_body": _(
            "En cas de danger immédiat, appelle le 112. "
            "HelpChain n’est pas un service d’urgence, mais nous traiterons ta demande en priorité."
        ),
        "success_title": _("Demande envoyée"),
        "success_body": _("Nous avons bien reçu ta demande. Nous te recontacterons dès que possible."),
        "success_next": _("Tu peux soumettre une nouvelle demande ou revenir à l’accueil."),
        "errors": {
            "too_many_requests_title": "Trop de requêtes",
            "too_many_requests_body": "Merci de patienter un instant puis de réessayer. Le système vous protège contre le spam et le flood.",
            "missing_category": _("Merci de choisir une catégorie."),
            "invalid_category": _("Catégorie invalide. Choisis dans la liste."),
            "missing_details": _("Merci de décrire brièvement la situation."),
            "details_too_short": _("La description est trop courte. Ajoute un peu de contexte."),
            "missing_contact": _("Merci de laisser un moyen de contact."),
            "invalid_contact": _("Le contact semble invalide. Vérifie téléphone/e-mail."),
            "missing_consent": _("Tu dois confirmer ton accord pour envoyer la demande."),
            "rate_limited": _("Trop de tentatives en peu de temps. Réessaie dans un instant."),
        },
    },
    categories={
        "food": {"title": _("Alimentation"), "hint": _("Besoin de courses, livraison ou soutien alimentaire.")},
        "emergency": {
            "title": _("Urgence"),
            "hint": _("Risque immédiat ou situation nécessitant une réaction rapide."),
            "is_emergency": True,
            "hotline": _("112"),
            "hotline_hint": _("En cas de danger immédiat, appelle le 112."),
        },
        "medical": {"title": _("Aide médicale"), "hint": _("Orientation, accompagnement, aide administrative liée aux soins.")},
        "legal": {"title": _("Aide juridique"), "hint": _("Conseils, documents, démarches, institutions.")},
        "shelter": {"title": _("Hébergement"), "hint": _("Solution temporaire, centre d’accueil, soutien de base.")},
        "education": {"title": _("Éducation"), "hint": _("Inscription, soutien scolaire/études, documents.")},
        "psychological": {"title": _("Soutien psychologique"), "hint": _("Aide en cas de stress, anxiété, situations de crise.")},
        "social": {"title": _("Aide sociale"), "hint": _("Services sociaux, aides, accompagnement, démarches.")},
        "elderly": {"title": _("Soutien aux personnes âgées"), "hint": _("Aide à domicile, courses, accompagnement, services.")},
        "disability": {"title": _("Handicap"), "hint": _("Accessibilité, services, démarches, aides techniques.")},
    },
    ,
    _lang="fr"
)


def get_copy(lang: str | None = None) -> CopyPack:
    """
    lang: 'bg' | 'fr' | anything else -> fallback bg
    Fallback strategy: FR falls back to BG per-key (so missing FR strings won't break UI).
    """
    l = (lang or "").lower()
    if l.startswith("fr"):
        merged_common = _deep_merge_fallback(COPY_FR.common, COPY_BG.common)
        merged_request = _deep_merge_fallback(COPY_FR.request, COPY_BG.request)
        merged_categories = _deep_merge_fallback(COPY_FR.categories, COPY_BG.categories)
        return CopyPack(common=merged_common, request=merged_request, categories=merged_categories, _lang="fr")
    # default BG
    return CopyPack(common=COPY_BG.common, request=COPY_BG.request, categories=COPY_BG.categories, _lang="bg")

# Single source of truth за UX copy
from typing import Any, Dict

class CopyPack:
    def __init__(self, data: Dict[str, Any]):
        self.__dict__.update(data)

# Български copy (MVP)
COPY_BG = CopyPack({
    "request": {
        "page_title": "Заявка за помощ",
        "intro": "Попълнете формата и ще се свържем с Вас при първа възможност.",
        "details_label": "Опишете накратко каква помощ Ви е нужна *",
        "details_help": "Колкото по-конкретно, толкова по-добре.",
        "contact_label": "Контакт (телефон или имейл) *",
        "submit_btn": "Изпрати заявка",
        "emergency_banner_title": "Спешен случай?",
        "emergency_banner_body": "Ако има непосредствена опасност, обади се на 112 или потърси компетентните органи.",
        "success": "Получихме заявката ти. Ще се свържем при първа възможност.",
        "generic_error": "Нещо се обърка. Опитай отново след малко.",
        "validation_error": "Провери маркираните полета и опитай отново.",
    },
    "common": {
        "cta_microcopy": "Отнема по-малко от 2 минути.",
        "emergency_number": "112",
    },
})

def get_copy(lang: str | None = None) -> CopyPack:
    # Засега само BG. По-късно: COPY_FR, COPY_EN и избор по lang.
    return COPY_BG

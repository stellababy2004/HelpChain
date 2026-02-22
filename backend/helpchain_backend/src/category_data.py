# Централен речник с всички категории, алиаси, общи текстове и schema version

CATEGORIES_SCHEMA_VERSION = 1

COMMON = {
    "trust_line": "Без регистрация • Безплатно • Дискретно",
    "cta_microcopy": "Отнема по-малко от 2 минути.",
    "emergency_number": "112",
    "not_found_title": "Категорията не е намерена",
    "not_found_btn": "Виж всички категории",
}

ALIASES = {
    "disaster": "emergency",
    "psych": "psychological",
    # добавяй още алиаси при нужда
}

CATEGORIES = {
    "food": {
        "canonical_slug": "food",
        "ui": {"icon": "fa-solid fa-bread-slice text-danger", "severity": "normal"},
        "content": {
            "title": {
                "bg": "Храна и хранителни продукти",
                "en": "Food and groceries",
                "fr": "Nourriture et produits alimentaires",
            },
            "intro": {
                "bg": "HelpChain съдейства с основни хранителни продукти и спешна хранителна подкрепа за семейства и уязвими хора.",
                "en": "HelpChain provides support with essential groceries and urgent food assistance for families and vulnerable people.",
                "fr": "HelpChain aide avec des produits alimentaires essentiels et un soutien alimentaire urgent pour les familles et les personnes vulnérables.",
            },
            "bullets": [
                "Основни хранителни продукти",
                "Спешна хранителна подкрепа",
                "Помощ за семейства и уязвими хора",
            ],
            "steps": [
                "Описваш нуждата си (форма)",
                "Ние поемаме координацията",
                "Свързваме с помощ",
            ],
            "notes": ["Помощта е доброволческа и според наличните възможности."],
            "cta": {
                "bg": "Подай заявка за хранителна помощ",
                "en": "Submit a food assistance request",
                "fr": "Déposer une demande d'aide alimentaire",
            },
        },
    },
    "emergency": {
        "canonical_slug": "emergency",
        "ui": {
            "icon": "fa-solid fa-triangle-exclamation text-danger",
            "severity": "critical",
        },
        "content": {
            "title": {
                "bg": "Помощ при бедствия и аварии",
                "en": "Disaster and emergency assistance",
                "fr": "Aide en cas de catastrophe et d'urgence",
            },
            "intro": {
                "bg": "HelpChain съдейства с координация, информация и допълваща подкрепа при бедствия и аварии.",
                "en": "HelpChain supports coordination, information, and additional assistance during disasters and emergencies.",
                "fr": "HelpChain aide à la coordination, à l'information et au soutien complémentaire lors de catastrophes et d'urgences.",
            },
            "bullets": [
                "Наводнения, пожари и природни бедствия",
                "Аварии в дома или района",
                "Извънредни ситуации, засягащи хора или семейства",
                "Нужда от координация и насочване към помощ",
                "Допълваща подкрепа след намеса на спешните служби",
            ],
            "steps": [
                "Описваш ситуацията (форма)",
                "Ние поемаме координацията",
                "Свързваме с помощ",
            ],
            "notes": [
                "HelpChain не замества спешните и аварийни служби. Платформата подпомага координацията и допълващата подкрепа."
            ],
            "emergency_line": "При непосредствена опасност за живота или здравето незабавно се обадете на 112.",
            "cta": {
                "bg": "Подай заявка за съдействие",
                "en": "Submit an assistance request",
                "fr": "Déposer une demande d'assistance",
            },
        },
    },
    # ... добави останалите категории по същия модел ...
}

# Можеш да разшириш CATEGORIES с още категории и езици по същия модел.

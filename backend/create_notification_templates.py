"""
Създаване на default notification templates за HelpChain
"""

# Try different import strategies
try:
    from notification_service import notification_service
except ImportError:
    try:
        from .notification_service import notification_service
    except ImportError:
        # For standalone execution
        import os
        import sys

        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from notification_service import notification_service


def create_default_templates():
    """Създава основните шаблони за нотификации"""

    templates = [
        # ====================================================================
        # REGISTRATION TEMPLATES
        # ====================================================================
        {
            "name": "welcome_email",
            "type": "email",
            "category": "registration",
            "subject": "🎉 Добре дошъл в HelpChain, {{ name }}!",
            "content": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa; padding: 20px;">
                <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <img src="https://helpchain.live/static/hands-heart.png" alt="HelpChain" style="width: 80px; height: 80px;">
                        <h1 style="color: #28a745; margin: 20px 0;">Добре дошъл в HelpChain!</h1>
                    </div>

                    <p style="font-size: 18px; color: #333; margin-bottom: 20px;">
                        Здравей <strong>{{ name }}</strong>,
                    </p>

                    <p style="font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 20px;">
                        Благодарим ти, че се присъедини към нашата общност от доброволци! 🤝
                        Твоята регистрация беше успешна и вече можеш да започнеш да помагаш на хора в нужда.
                    </p>

                    <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #28a745; margin-top: 0;">📋 Твоите данни:</h3>
                        <ul style="color: #555; line-height: 1.8;">
                            <li><strong>Име:</strong> {{ name }}</li>
                            <li><strong>Email:</strong> {{ email }}</li>
                            <li><strong>Телефон:</strong> {{ phone }}</li>
                            <li><strong>Град:</strong> {{ city }}</li>
                        </ul>
                    </div>

                    <p style="font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 20px;">
                        🎯 <strong>Какво следва?</strong><br>
                        Нашият екип ще прегледа твоята регистрация в рамките на 24-48 часа.
                        След одобрението ще получиш имейл с инструкции за следващите стъпки.
                    </p>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://helpchain.live/"
                           style="background-color: #28a745; color: white; padding: 15px 30px;
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  font-size: 16px; display: inline-block;">
                            🏠 Посети HelpChain
                        </a>
                    </div>

                    <div style="border-top: 2px solid #e9ecef; padding-top: 20px; margin-top: 30px; text-align: center;">
                        <p style="color: #666; font-size: 14px; margin-bottom: 10px;">
                            ❤️ Благодарим ти за желанието да помагаш!
                        </p>
                        <p style="color: #888; font-size: 12px;">
                            HelpChain - Свързваме сърца, променяме живота
                        </p>
                    </div>
                </div>
            </div>
            """,
            "variables": ["name", "email", "phone", "city"],
            "priority": "high",
            "auto_send": True,
        },
        {
            "name": "registration_approved",
            "type": "email",
            "category": "registration",
            "subject": "✅ Регистрацията ти в HelpChain е одобрена!",
            "content": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa; padding: 20px;">
                <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <div style="background-color: #28a745; color: white; width: 80px; height: 80px;
                                    border-radius: 50%; display: flex; align-items: center; justify-content: center;
                                    margin: 0 auto 20px; font-size: 30px;">✅</div>
                        <h1 style="color: #28a745; margin: 0;">Регистрацията одобрена!</h1>
                    </div>

                    <p style="font-size: 18px; color: #333; margin-bottom: 20px;">
                        Поздравления, <strong>{{ name }}</strong>!
                    </p>

                    <p style="font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 20px;">
                        Твоята регистрация като доброволец в HelpChain беше успешно одобрена! 🎉
                        Сега можеш да започнеш да помагаш на хора в нужда и да правиш разлика в общността.
                    </p>

                    <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                        <h3 style="color: #856404; margin-top: 0;">🚀 Следващи стъпки:</h3>
                        <ol style="color: #856404; line-height: 1.8;">
                            <li>Посети нашия сайт и разгледай наличните възможности за помощ</li>
                            <li>Използвай нашия AI чатбот за въпроси и съвети</li>
                            <li>Свържи се с нас при нужда от помощ или информация</li>
                            <li>Сподели HelpChain със семейството и приятелите си</li>
                        </ol>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://helpchain.live/"
                           style="background-color: #28a745; color: white; padding: 15px 30px;
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  font-size: 16px; display: inline-block; margin-right: 10px;">
                            🏠 Започни сега
                        </a>
                        <a href="https://helpchain.live/chatbot"
                           style="background-color: #007bff; color: white; padding: 15px 30px;
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  font-size: 16px; display: inline-block;">
                            🤖 AI Помощник
                        </a>
                    </div>

                    <p style="color: #666; font-size: 14px; text-align: center; margin-top: 30px;">
                        Благодарим ти за доверието и желанието да помагаш! ❤️
                    </p>
                </div>
            </div>
            """,
            "variables": ["name"],
            "priority": "high",
        },
        # ====================================================================
        # FEEDBACK TEMPLATES
        # ====================================================================
        {
            "name": "feedback_received",
            "type": "email",
            "category": "feedback",
            "subject": "💌 Благодарим за обратната връзка!",
            "content": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa; padding: 20px;">
                <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <div style="font-size: 60px; margin-bottom: 20px;">💌</div>
                        <h1 style="color: #007bff; margin: 0;">Обратната връзка получена!</h1>
                    </div>

                    <p style="font-size: 18px; color: #333; margin-bottom: 20px;">
                        Здравей {{ name }},
                    </p>

                    <p style="font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 20px;">
                        Благодарим ти за отделеното време да споделиш мнението си с нас!
                        Твоята обратна връзка е изключително ценна и ни помага да подобряваме HelpChain.
                    </p>

                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #007bff;">
                        <h3 style="color: #495057; margin-top: 0;">📝 Твоето мнение:</h3>
                        <p style="color: #6c757d; font-style: italic; line-height: 1.6;">
                            "{{ feedback_text }}"
                        </p>
                        {% if rating %}
                        <p style="color: #495057; margin-top: 15px;">
                            <strong>Оценка:</strong>
                            <span style="color: #ffc107; font-size: 18px;">
                                {% for i in range(rating) %}⭐{% endfor %}
                            </span>
                            ({{ rating }}/5)
                        </p>
                        {% endif %}
                    </div>

                    <p style="font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 20px;">
                        Нашият екип ще прегледа твоята обратна връзка и ако е необходимо,
                        ще се свържем с теб за допълнителни въпроси или разяснения.
                    </p>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://helpchain.live/"
                           style="background-color: #007bff; color: white; padding: 15px 30px;
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  font-size: 16px; display: inline-block;">
                            🏠 Обратно към HelpChain
                        </a>
                    </div>

                    <p style="color: #666; font-size: 14px; text-align: center; margin-top: 30px;">
                        Заедно създаваме по-добра общност! 🤝
                    </p>
                </div>
            </div>
            """,
            "variables": ["name", "feedback_text", "rating"],
            "priority": "normal",
        },
        # ====================================================================
        # PUSH NOTIFICATION TEMPLATES
        # ====================================================================
        {
            "name": "welcome_push",
            "type": "push",
            "category": "registration",
            "title": "🎉 Добре дошъл в HelpChain!",
            "content": "Благодарим ти за регистрацията, {{ name }}! Започни да помагаш още сега.",
            "variables": ["name"],
            "priority": "normal",
        },
        {
            "name": "new_feature_push",
            "type": "push",
            "category": "system",
            "title": "🆕 Нова функционалност в HelpChain",
            "content": "Провери новите възможности за помощ и подкрепа в платформата.",
            "variables": [],
            "priority": "low",
        },
        # ====================================================================
        # IN-APP NOTIFICATION TEMPLATES
        # ====================================================================
        {
            "name": "registration_pending",
            "type": "in_app",
            "category": "registration",
            "title": "⏳ Регистрацията се обработва",
            "content": "Твоята регистрация е получена и ще бъде прегледана в рамките на 24-48 часа.",
            "variables": [],
            "priority": "normal",
        },
        {
            "name": "system_maintenance",
            "type": "in_app",
            "category": "system",
            "title": "🔧 Планирана поддръжка",
            "content": "Системата ще бъде недостъпна за кратко време поради поддръжка на {{ date }}.",
            "variables": ["date"],
            "priority": "high",
        },
    ]

    print("📋 Създаване на default notification templates...")

    created_count = 0
    for template_data in templates:
        try:
            # Проверяваме дали шаблонът вече съществува
            existing = notification_service.get_template(template_data["name"])
            if existing:
                print(f"⚠️  Шаблон '{template_data['name']}' вече съществува")
                continue

            # Създаваме новия шаблон
            _template = notification_service.create_template(**template_data)
            created_count += 1
            print(f"✅ Създаден: {template_data['name']} ({template_data['type']})")

        except Exception as e:
            print(f"❌ Грешка при създаване на '{template_data['name']}': {str(e)}")

    print(f"\n🎉 Създадени {created_count} нови шаблона от общо {len(templates)}!")
    return created_count


if __name__ == "__main__":
    # Стартираме в Flask context
    from appy import app

    with app.app_context():
        create_default_templates()

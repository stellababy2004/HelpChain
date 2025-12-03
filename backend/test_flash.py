from appy import app
from dotenv import load_dotenv
from flask import flash, get_flashed_messages

load_dotenv()


# Тестов скрипт за симулация на различни flash съобщения
def test_flash_messages():
    # използваме test_request_context, за да има активна сесия/контекст
    with app.test_request_context():
        flash("✅ Това е success съобщение!", "success")
        messages = get_flashed_messages(with_categories=True)
        assert ("success", "✅ Това е success съобщение!") in messages


test_flash_messages()

print("✅ Тестът на flash съобщенията е успешен!")

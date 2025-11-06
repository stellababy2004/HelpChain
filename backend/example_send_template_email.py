# Example: How to use _dispatch_email with a template and context
from _dispatch_email import _dispatch_email

# Example context for the template
template_context = {
    "recipient_name": "Иван Иванов",
    "custom_message": "Благодарим ви, че се регистрирахте в HelpChain!",
    "action_url": "https://helpchain.bg/activate/abc123",
}

# Call _dispatch_email with template and context
_dispatch_email(
    subject="Добре дошли в HelpChain!",
    recipients=["ivan.ivanov@example.com"],
    body="Това е fallback текст, ако HTML не се зареди.",
    template="welcome_email.html",  # This should be a Jinja2 template in your templates/ папка
    context=template_context,
)

# In your templates/welcome_email.html:
#
# <html>
# <body>
#   <h2>Здравейте, {{ recipient_name }}!</h2>
#   <p>{{ custom_message }}</p>
#   <a href="{{ action_url }}">Активирайте профила си</a>
# </body>
# </html>

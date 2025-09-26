# 🌐 HelpChain Multilingual System - Quick Reference Guide

## 📋 **Essential Commands & Usage**

### 🚀 **Start HelpChain**
```bash
cd "C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend"
python appy.py
```

### 🌍 **Access Points**
- **Main App**: http://localhost:5000
- **Admin Panel**: http://localhost:5000/admin_quick_login
- **Translation Dashboard**: http://localhost:5000/admin/translations
- **Analytics Dashboard**: http://localhost:5000/admin/analytics
- **Notifications Dashboard**: http://localhost:5000/admin/notifications

---

## 🔤 **Translation System Usage**

### 📝 **In HTML Templates**
```html
<!-- Basic translation -->
{{ t('welcome.title') }}           <!-- "Добре дошли в HelpChain" -->
{{ t('nav.home') }}               <!-- "Начало" -->
{{ t('common.save') }}            <!-- "Запази" -->

<!-- With variables -->
{{ t('welcome.user', name=user.name) }}  <!-- "Добре дошли, Стела!" -->

<!-- Date/Time formatting -->
{{ format_date(datetime.now()) }}  <!-- "24.09.2025" -->
{{ format_time(datetime.now()) }}  <!-- "15:30" -->
```

### 🌐 **Language Switching (JavaScript)**
```javascript
// Switch language
async function switchLanguage(languageCode) {
    const response = await fetch('/api/translations/switch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            language_code: languageCode,
            user_id: getCurrentUserId()  // optional
        })
    });
    
    if (response.ok) {
        location.reload();  // Reload to apply new language
    }
}

// Get available languages
async function getLanguages() {
    const response = await fetch('/api/languages');
    const data = await response.json();
    return data.languages;
}

// Get translations for specific keys
async function getTranslations(languageCode, keys) {
    const keysList = keys.join(',');
    const response = await fetch(`/api/translations/${languageCode}?keys=${keysList}`);
    return await response.json();
}
```

### 🤖 **AI Translation (Python)**
```python
from translation_service import translation_service

# Auto-translate missing keys to English
translated_count = translation_service.auto_translate_missing(
    target_language_code='en',
    source_language_code='bg', 
    max_translations=50
)

# Add manual translation
translation_service.add_translation(
    key='new.key',
    language_code='en',
    translated_text='Hello World',
    status='approved'
)

# Get translation
text = translation_service.get_translation('welcome.title', 'en')
```

---

## 📊 **Analytics System**

### 📈 **Track Events**
```python
from analytics_service import analytics_service

# Track user action
analytics_service.track_event(
    event_type='user_action',
    category='volunteer',
    action='registration',
    label='new_volunteer',
    context={'user_id': 123, 'source': 'web'}
)

# Track performance
analytics_service.track_performance(
    metric_name='page_load_time',
    category='performance',
    value=1.25,
    unit='seconds'
)
```

### 📊 **Get Analytics Data**
```python
# Get dashboard data
stats = analytics_service.get_dashboard_data(days=30)

# Get conversion funnel
funnel = analytics_service.get_conversion_funnel(['page_view', 'form_submit', 'registration'])
```

---

## 🔔 **Notification System**

### 📧 **Send Notifications**
```python
from notification_service import notification_service

# Send email notification
notification_service.send_notification(
    template_name='welcome_volunteer',
    recipient_email='user@example.com',
    personalization_data={
        'volunteer_name': 'Стела',
        'registration_date': '24.09.2025'
    },
    priority='high'
)

# Queue notification for later
notification_service.queue_notification(
    template_name='reminder',
    recipient_email='user@example.com',
    scheduled_for=datetime.now() + timedelta(hours=24)
)
```

### 📱 **Notification Templates**
```python
# Create notification template
template = NotificationTemplate(
    name='custom_notification',
    type='email',
    subject='{{title}}',
    body_html='<h1>{{message}}</h1>',
    variables=['title', 'message']
)
```

---

## 🗄️ **Database Operations**

### 🔧 **Initialize Systems**
```bash
# Initialize multilingual system
python init_multilingual.py

# Create notification templates
python create_notification_templates.py

# Initialize all tables
python -c "from appy import app, db; app.app_context().push(); db.create_all()"
```

### 📊 **Database Models Quick Access**
```python
from models import (
    Volunteer, HelpRequest, 
    SupportedLanguage, Translation, TranslationKey,
    NotificationTemplate, NotificationQueue,
    AnalyticsEvent, AnalyticsMetric
)

# Query examples
volunteers = Volunteer.query.filter_by(status='active').all()
languages = SupportedLanguage.query.filter_by(is_active=True).all()
pending_notifications = NotificationQueue.query.filter_by(status='pending').all()
```

---

## 🔍 **API Endpoints Reference**

### 🌐 **Multilingual API**
```bash
# Get supported languages
GET /api/languages

# Get translations
GET /api/translations/bg?keys=nav.home,nav.about

# Switch language
POST /api/translations/switch
Body: {"language_code": "en", "user_id": 123}

# Get translation stats
GET /api/translations/stats
```

### 📊 **Analytics API** 
```bash
# Get analytics data
GET /api/analytics/dashboard?days=30

# Track event
POST /api/analytics/track
Body: {"event_type": "user_action", "category": "volunteer", "action": "click"}
```

### 🔔 **Notifications API**
```bash
# Send notification
POST /api/notifications/send
Body: {"template_name": "welcome", "recipient_email": "user@example.com"}

# Get queue status
GET /api/notifications/queue/status

# Get templates
GET /api/notifications/templates
```

---

## 🛠️ **Common Tasks**

### 🌍 **Add New Language**
```python
# 1. Add to database
new_language = SupportedLanguage(
    code='it',
    name='Italian', 
    native_name='Italiano',
    flag_emoji='🇮🇹',
    currency_code='EUR'
)

# 2. Use AI to translate
translation_service.auto_translate_missing('it', 'bg', 100)
```

### 🔤 **Add New Translation Keys**
```python
# Register new key
translation_service.register_translation_key(
    key='new.feature.title',
    source_text='Нова функционалност',
    category='ui',
    description='Title for new feature section'
)
```

### 📧 **Create Custom Email Template**
```html
<!-- In email_templates/ folder -->
<h1>{{title}}</h1>
<p>Здравейте {{volunteer_name}},</p>
<p>{{message}}</p>
<a href="{{action_url}}">{{action_text}}</a>
```

---

## 🚨 **Troubleshooting**

### 🔧 **Common Issues**
```bash
# If server won't start
Get-Process -Name 'python' | Stop-Process -Force

# If database issues
python -c "from appy import app, db; app.app_context().push(); db.drop_all(); db.create_all()"

# If translation issues
python init_multilingual.py

# If notification issues  
python create_notification_templates.py
```

### 📝 **Debug Mode**
```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test specific service
from translation_service import translation_service
print(translation_service.get_translation_stats())
```

---

## 🎯 **Quick Testing Commands**

### ✅ **Test Translation System**
```python
python -c "
from translation_service import translation_service, t
print('BG:', t('welcome.title', 'bg'))
print('EN:', t('welcome.title', 'en'))
print('Stats:', translation_service.get_translation_stats())
"
```

### ✅ **Test Notification System**
```python  
python -c "
from notification_service import notification_service
result = notification_service.send_test_notification('test@example.com')
print('Test result:', result)
"
```

### ✅ **Test Analytics System**
```python
python -c "
from analytics_service import analytics_service
analytics_service.track_event('test', 'system', 'startup', 'manual')
stats = analytics_service.get_dashboard_data(7)
print('Events today:', len(stats.get('recent_events', [])))
"
```

---

## 🔑 **Key File Locations**

### 📁 **Core Files**
- `appy.py` - Main Flask application
- `models.py` - Database models
- `translation_service.py` - Translation system
- `notification_service.py` - Notification system  
- `analytics_service.py` - Analytics system

### 📁 **Templates**
- `templates/` - HTML templates
- `email_templates/` - Email templates
- `static/` - CSS, JS, images

### 📁 **Admin Dashboards**
- `templates/admin_translations_dashboard.html`
- `templates/admin_analytics_dashboard.html`
- `templates/notifications_dashboard.html`

### 📁 **Configuration**
- `.env` - Environment variables
- `requirements.txt` - Python dependencies
- `babel.cfg` - Babel configuration

---

## 💡 **Pro Tips**

1. **Always use `t()` function** for user-visible text
2. **Test translations** in multiple languages before deployment
3. **Monitor notification queue** to avoid email overload
4. **Use analytics events** to track user behavior
5. **Regular backup** of translation database
6. **AI translations** need review before going live

---

## 🎉 **Ready to Use!**

Your HelpChain platform now has:
- ✅ **6 languages** (BG, EN, DE, FR, ES, RU)
- ✅ **AI-powered translations**
- ✅ **Advanced analytics**
- ✅ **Multi-channel notifications**
- ✅ **Admin dashboards**

**Start the server and explore!** 🚀
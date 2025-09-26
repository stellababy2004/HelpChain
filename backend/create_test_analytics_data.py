"""
Създаване на тестова база данни с разнообразни потребители и заявки за analytics тестване
"""
import sys
import os
from datetime import datetime, timedelta
import random
from faker import Faker

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from appy import app, db
from models import Volunteer, HelpRequest, AnalyticsEvent

fake = Faker('bg_BG')  # Bulgarian locale

def create_test_database():
    """Създава тестова база данни с разнообразни данни"""
    
    with app.app_context():
        # Създаваме нови тестови данни без изтриване на стари
        print("📝 Създаване на нови тестови данни...")
        
        # Категории помощ
        help_categories = [
            'Транспорт',
            'Домакински грижи', 
            'Медицинска помощ',
            'Пазаруване',
            'Техническа поддръжка',
            'Преводи',
            'Обучение',
            'Психологическа подкрепа',
            'Юридическа консултация',
            'Грижа за възрастни',
            'Грижа за деца',
            'Социални дейности'
        ]
        
        # Български градове
        bulgarian_cities = [
            'София', 'Пловдив', 'Варна', 'Бургас', 'Русе',
            'Стара Загора', 'Плевен', 'Сливен', 'Добрич', 'Шумен',
            'Перник', 'Хасково', 'Ямбол', 'Пазарджик', 'Благоевград',
            'Велико Търново', 'Враца', 'Габрово', 'Асеновград', 'Видин',
            'Казанлък', 'Кърджали', 'Кюстендил', 'Монтана', 'Димитровград'
        ]
        
        # Статуси на заявки
        request_statuses = ['Активен', 'Завършена', 'В процес', 'Отказана', 'Чака потвърждение']
        
        # Умения и специализации
        skills_list = [
            'Шофиране', 'Готвене', 'Почистване', 'Градинарство', 'Ремонти',
            'Преводи', 'Компютърни услуги', 'Медицински грижи', 'Психология',
            'Юридически въпроси', 'Обучение', 'Музика', 'Изкуство', 'Спорт',
            'Бизнес консултиране', 'Счетоводство', 'Инженерство', 'Архитектура'
        ]
        
        print("👥 Създаване на тестови доброволци...")
        
        # Създаване на тестови доброволци
        volunteers = []
        for i in range(50):
            volunteer = Volunteer(
                name=f"[TEST] {fake.first_name()} {fake.last_name()}",
                email=f"test.volunteer{i+1}@helpchain-test.bg",
                phone=fake.phone_number()[:15],
                location=random.choice(bulgarian_cities),
                skills=', '.join(random.sample(skills_list, random.randint(2, 5))),
                availability=random.choice(['Седмични дни', 'Уикенди', 'Всеки ден', 'По договаряне']),
                bio=f"Тестов доброволец с опит в {random.choice(help_categories).lower()}. {fake.text(max_nb_chars=100)}",
                verified=random.choice([True, False]),
                active=random.choice([True, True, True, False]),  # 75% активни
                created_at=fake.date_time_between(start_date='-6M', end_date='now')
            )
            volunteers.append(volunteer)
            db.session.add(volunteer)
        
        db.session.commit()
        print(f"✅ Създадени {len(volunteers)} тестови доброволци")
        
        print("📝 Създаване на тестови заявки за помощ...")
        
        # Създаване на тестови заявки за помощ
        help_requests = []
        for i in range(120):
            created_at = fake.date_time_between(start_date='-3M', end_date='now')
            
            # Примерни заглавия и описания базирани на категорията
            category = random.choice(help_categories)
            
            titles_by_category = {
                'Транспорт': ['Нуждая се от превоз до болница', 'Помощ за товарене на мебели', 'Превоз до летище'],
                'Домакински грижи': ['Почистване на апартамент', 'Помощ с пране', 'Организиране на дом'],
                'Медицинска помощ': ['Придружаване до лекар', 'Помощ с лекарства', 'Рехабилитация'],
                'Пазаруване': ['Пазаруване на хранителни стоки', 'Покупка на лекарства', 'Избор на подарък'],
                'Техническа поддръжка': ['Ремонт на компютър', 'Инсталиране на софтуер', 'Настройка на WiFi'],
                'Преводи': ['Превод на документи', 'Устен превод', 'Помощ с кореспонденция'],
                'Обучение': ['Урок по математика', 'Помощ с английски език', 'Компютърна грамотност'],
                'Психологическа подкрепа': ['Разговор при трудности', 'Емоционална подкрепа', 'Консултация'],
                'Юридическа консултация': ['Помощ с документи', 'Правни съвети', 'Съдействие с процедури'],
                'Грижа за възрастни': ['Придружаване на възрастен човек', 'Помощ в ежедневието', 'Социализация'],
                'Грижа за деца': ['Детегледане', 'Помощ с домашни', 'Развлечения за деца'],
                'Социални дейности': ['Организиране на събиране', 'Културни активности', 'Доброволчески проект']
            }
            
            title = random.choice(titles_by_category.get(category, ['Обща помощ']))
            
            help_request = HelpRequest(
                name=f"[TEST] {fake.first_name()} {fake.last_name()}",
                email=f"test.requester{i+1}@helpchain-test.bg",
                phone=fake.phone_number()[:15],
                title=title,
                description=f"[TEST] {fake.text(max_nb_chars=200)}",
                location=random.choice(bulgarian_cities),
                category=category,
                urgency=random.choice(['Нисък', 'Среден', 'Висок', 'Спешен']),
                status=random.choice(request_statuses),
                created_at=created_at,
                updated_at=created_at + timedelta(days=random.randint(0, 30))
            )
            
            # Добавяне на assigned_volunteer_id за част от заявките
            if help_request.status in ['В процес', 'Завършена'] and volunteers:
                help_request.assigned_volunteer_id = random.choice(volunteers).id
            
            help_requests.append(help_request)
            db.session.add(help_request)
        
        db.session.commit()
        print(f"✅ Създадени {len(help_requests)} тестови заявки за помощ")
        
        print("📊 Създаване на тестови analytics събития...")
        
        # Типове събития за analytics
        event_types = [
            'page_view', 'user_action', 'form_interaction', 
            'feature_usage', 'search', 'registration', 'login'
        ]
        
        event_categories = [
            'navigation', 'volunteer', 'admin', 'ui', 'search', 
            'registration', 'authentication', 'help_request'
        ]
        
        # User types
        user_types = ['guest', 'volunteer', 'admin', 'requester']
        
        # Популярни страници
        popular_pages = [
            '/dashboard', '/volunteers', '/admin', '/register', '/login',
            '/help-requests', '/profile', '/analytics', '/search', '/about'
        ]
        
        # Създаване на analytics събития
        analytics_events = []
        for i in range(800):
            event_time = fake.date_time_between(start_date='-30d', end_date='now')
            
            event_type = random.choice(event_types)
            category = random.choice(event_categories)
            
            # Различни действия базирани на типа
            actions_by_type = {
                'page_view': ['visit', 'load', 'refresh'],
                'user_action': ['click', 'submit', 'download', 'share'],
                'form_interaction': ['form_start', 'form_submit', 'form_error'],
                'feature_usage': ['search', 'filter', 'export', 'sort'],
                'search': ['search_query', 'search_results', 'search_filter'],
                'registration': ['registration_start', 'registration_complete'],
                'login': ['login_attempt', 'login_success', 'logout']
            }
            
            action = random.choice(actions_by_type.get(event_type, ['generic_action']))
            
            # Метаданни базирани на типа събитие
            if event_type == 'page_view':
                page = random.choice(popular_pages)
                metadata = f'{{"page": "{page}", "test": true, "referrer": "direct", "load_time": {random.randint(200, 2000)}}}'
            elif event_type == 'search':
                search_terms = ['помощ София', 'доброволец Пловдив', 'транспорт', 'медицинска помощ', 'преводи']
                term = random.choice(search_terms)
                metadata = f'{{"search_term": "{term}", "test": true, "results_count": {random.randint(0, 50)}}}'
            else:
                metadata = f'{{"test": true, "session_id": "test_session_{random.randint(1000, 9999)}", "user_agent": "TestAgent"}}'
            
            analytics_event = AnalyticsEvent(
                event_type=event_type,
                event_category=category,
                event_action=action,
                event_label=f"test_{random.choice(user_types)}",
                event_value=random.randint(1, 100),
                user_session=f"test_session_{random.randint(1000, 9999)}",
                user_type=random.choice(user_types),
                user_ip=fake.ipv4(),
                user_agent="TestUserAgent/1.0",
                referrer=random.choice([None, 'https://google.com', 'https://facebook.com', 'direct']),
                page_url=random.choice(popular_pages),
                page_title=f"Test Page - {random.choice(popular_pages).replace('/', '')}",
                load_time=random.uniform(0.2, 3.0),
                screen_resolution=random.choice(['1920x1080', '1366x768', '1440x900', '1536x864']),
                device_type=random.choice(['desktop', 'mobile', 'tablet']),
                created_at=event_time
            )
            
            analytics_events.append(analytics_event)
            db.session.add(analytics_event)
        
        db.session.commit()
        print(f"✅ Създадени {len(analytics_events)} тестови analytics събития")
        
        # Статистика за създадените данни
        print("\n📈 Обобщение на създадените тестови данни:")
        print(f"  👥 Доброволци: {len(volunteers)}")
        print(f"  📝 Заявки за помощ: {len(help_requests)}")
        print(f"  📊 Analytics събития: {len(analytics_events)}")
        
        # Разпределение по категории
        category_count = {}
        for req in help_requests:
            category_count[req.category] = category_count.get(req.category, 0) + 1
        
        print(f"\n🏷️ Разпределение по категории:")
        for category, count in sorted(category_count.items()):
            print(f"  • {category}: {count} заявки")
        
        # Разпределение по градове
        city_count = {}
        for req in help_requests:
            city_count[req.location] = city_count.get(req.location, 0) + 1
        
        print(f"\n🏙️ Топ 10 градове по брой заявки:")
        for city, count in sorted(city_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  • {city}: {count} заявки")
        
        # Разпределение по статуси
        status_count = {}
        for req in help_requests:
            status_count[req.status] = status_count.get(req.status, 0) + 1
        
        print(f"\n📊 Разпределение по статуси:")
        for status, count in sorted(status_count.items()):
            print(f"  • {status}: {count} заявки")
            
        print(f"\n🎯 Тестовата база данни е готова!")
        print(f"💡 Всички тестови записи са маркирани с '[TEST]' в името/описанието")
        print(f"🔍 Сега можете да тествате филтрите в Analytics Dashboard!")

if __name__ == "__main__":
    print("🚀 Създаване на тестова база данни за HelpChain Analytics...")
    create_test_database()
    print("✅ Завършено успешно!")
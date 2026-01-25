from backend.helpchain_backend.src.app import create_app
app = create_app()
with app.app_context():
    from backend.extensions import db
    import backend.models as m
    # trigger mapper configure safely
    print('metadata tables:', len(db.metadata.tables))
    print('User has push_subscriptions:', hasattr(m.User, 'push_subscriptions'))
    print('PushSubscription has user:', hasattr(m.PushSubscription, 'user'))

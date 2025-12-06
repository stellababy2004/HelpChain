import sys

sys.path.insert(0, r'c:\dev\HelpChain\HelpChain.bg')
try:
    import backend.models as m
    print('HelpRequest present:', hasattr(m, 'HelpRequest'))
    print('NotificationPreference present:', hasattr(m, 'NotificationPreference'))
    print('Request present:', hasattr(m, 'Request'))
    print('NotificationTemplate present:', hasattr(m, 'NotificationTemplate'))
except Exception as e:
    print('IMPORT ERROR:', e)

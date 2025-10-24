#!/usr/bin/env python3
"""
Check Flask-Compress configuration
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from appy import app
    print('✅ Flask-Compress configuration check:')
    print(f'   COMPRESS_MIMETYPES: {app.config.get("COMPRESS_MIMETYPES")}')
    print(f'   COMPRESS_LEVEL: {app.config.get("COMPRESS_LEVEL")}')
    print(f'   COMPRESS_MIN_SIZE: {app.config.get("COMPRESS_MIN_SIZE")}')

    # Check if compress extension is registered
    from flask_compress import Compress
    compress_ext = None
    for ext in app.extensions.values():
        if isinstance(ext, Compress):
            compress_ext = ext
            break

    if compress_ext:
        print('✅ Flask-Compress extension is registered and initialized')
    else:
        print('❌ Flask-Compress extension not found in app.extensions')

except Exception as e:
    print(f'❌ Error checking configuration: {e}')
    import traceback
    traceback.print_exc()
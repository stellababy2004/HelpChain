Development startup instructions:

1) `python backend/scripts/dev_reset.py`  
   Deletes old dev databases, recreates `backend/instance/app.db`, runs migrations,
   and creates the default admin user.

2) `python backend/scripts/system_health.py`  
   Verifies database connection, required tables, admin user, routes, and migrations.

3) `flask --app backend.appy:app run`  
   Starts the Flask development server.

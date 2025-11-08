# HelpChain.bg – Quick Start Guide (Windows)

## 1. Start Redis (if not running)

```
docker start helpchain-redis
```

If the container does not exist:

```
docker run -d --name helpchain-redis -p 6379:6379 redis:7
```

---

## 2. Activate Python virtual environment

```
& ".venv/Scripts/Activate.ps1"
```

---

## 3. Start Celery worker (new terminal)

```
celery -A celery_app worker --loglevel=info --pool=solo
```

---

## 4. Start Celery beat (new terminal)

```
celery -A celery_app beat --loglevel=info
```

---

## 5. Start Flask backend (new terminal)

```
python appy.py
```

(or `python main.py` if your entry point is different)

---

## 6. Open in browser

http://127.0.0.1:5000/

---

## Notes

- Always use `--pool=solo` for Celery worker on Windows.
- Make sure Redis is running before starting Celery.
- Use separate terminals for each service.

---

## Troubleshooting

- If you see errors about Redis, check that the Docker container is running.
- If Celery worker fails on Windows, double-check the `--pool=solo` option.
- For production, use Linux/WSL for better performance.

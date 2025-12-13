# Vercel разгръщане - бележки и препоръки

Този файл описва как Vercel клонира/изгражда проекта и защо добавихме `runtime.txt` и променихме `vercel.json`.

## Проблеми, които адресираме

- Vercel предупреждава: "No Python version specified" — Vercel по подразбиране използва най-новата налична Python версия. За репликативни билдове е полезно да пиннем версия.
- "Failed to fetch one or more git submodules" — в този хранилище няма `.gitmodules`, така че това вероятно е временна/удалена конфигурация на remote или приватен submodule, недостъпен за Vercel.
- "Due to `builds` existing in your configuration file, the Project Settings Build and Development Settings will not apply" — когато използваме `vercel.json` с `builds`, настройките в уеб интерфейса за билд не се прилагат.

## Какво направихме

- Добавен `runtime.txt` с `python-3.12.18` за пиннати билдове на Vercel.
- Актуализирахме `vercel.json` да използва `backend/app.py` като входна точка вместо deprecated `backend/appy.py`.

## Препоръки

- Ако приложението трябва да работи като постоянно стартиран процес (Uvicorn/Long-running Flask), обмислете използване на платформа, която поддържа persistent services (например Render, Railway или Docker-based deployment). Vercel е оптимизиран за serverless функции и кратки процеси.

- Ако имате приватни submodules, добавете deploy key или премахнете/заменете submodule-ите преди build. Проверките локално:

```bash
git submodule status --recursive
git config --file .gitmodules --list || echo "no .gitmodules"
```

- Можете да редактирате Project Settings в Vercel и да премахнете `builds` от `vercel.json` ако предпочитате да управлявате билд конфигурацията чрез UI.

## Предложен PR

Заглавие: `chore: pin Python runtime and update Vercel entrypoint`
Описание: "Добавя `runtime.txt` (python-3.12.18), актуализира `vercel.json` да сочи `backend/app.py` и добавя VERCEL_DEPLOYMENT.md с обяснения и препоръки за Vercel разгръщане."

---

Ако желаете, мога да:
- Създам Pull Request директно в репото (pushнах промените в branch `fix/vercel-config`).
- Или да направя допълнителни промени в `vercel.json` (например задаване на стартираща команда). 

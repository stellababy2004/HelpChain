# Install инструкции (conda-first, Windows / PowerShell)

Тези инструкции създават конда среда, която управлява тежките бинарни пакети (numpy, pandas, scipy, opencv и т.н.), след което използват pip за останалите зависимости.

1) Създаване на средата от `environment.yml`:

```powershell
conda env create -f environment.yml
conda activate helpchain
```

2) Подгответе constraints файл (използвайте ваш `constraints_clean.txt` и премахнете тежките пакети):

```powershell
# ако имате constraints_clean.txt, създайте sanitized версия:
Get-Content .\constraints_clean.txt | Where-Object { $_ -notmatch '^(numpy|pandas|scipy|scikit-learn|opencv|opencv-python|joblib)==' } | Set-Content .\constraints_sanitized.txt
```

3) Инсталирайте останалите пакети с pip (в средата `helpchain`):

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-pip.txt -c constraints_sanitized.txt
```

4) Ако срещнете допълнителни конфликти:
- Можете да премахнете още heavy пакети от `constraints_sanitized.txt` (например `joblib`, `opencv-python`) и да опитате отново.
- Като алтернатива, кажете ми и аз ще подготвя PR с обновена версия на `constraints_sanitized.txt` и/или ще предложа конкретни версии за уеднаквяване.

5) Add/commit & PR (предложение):

```powershell
git checkout -b fix/add-environment-yml
git add environment.yml requirements-pip.txt INSTALL.md
git commit -m "chore: add conda environment.yml and pip-only requirements file + install docs"
git push -u origin fix/add-environment-yml
# create PR via GitHub web or gh cli:
gh pr create --title "chore: add conda environment + install docs" --body "Adds conda environment.yml, pip-only requirements and INSTALL.md with recommended install steps."
```

---
If предпочиташ, мога да отворя PR от името ти (ако имам подходящ достъп), или да подготвя още малки промени преди PR (напр. `constraints_sanitized.txt`).

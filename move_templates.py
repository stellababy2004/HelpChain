import os
import shutil

# Пътища
frontend = os.path.join("frontend")
templates = os.path.join("backend", "templates")

# Създаване на templates папка ако не съществува
os.makedirs(templates, exist_ok=True)

# Преместване на всички .html файлове
for file in os.listdir(frontend):
    if file.endswith(".html"):
        src = os.path.join(frontend, file)
        dst = os.path.join(templates, file)
        shutil.move(src, dst)
        print(f"✅ Преместен: {file}")

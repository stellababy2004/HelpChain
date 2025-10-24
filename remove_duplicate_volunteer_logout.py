#!/usr/bin/env python3
import re

# Read the file
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    encoding="utf-8",
) as f:
    content = f.read()

# Find the second volunteer_logout function and remove it
# Look for the pattern: @app.route("/volunteer_logout") followed by the function, then the next comment ===== ADMIN MANAGEMENT ROUTES =====
pattern = r'(@app\.route\("/volunteer_logout"\)\s*def volunteer_logout\(\):.*?(?=# ===== ADMIN MANAGEMENT ROUTES =====))'

# Use DOTALL to match across lines
match = re.search(pattern, content, re.DOTALL)
if match:
    content = content.replace(match.group(0), "")

# Write back
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    "w",
    encoding="utf-8",
) as f:
    f.write(content)

print("Duplicate volunteer_logout function removed")

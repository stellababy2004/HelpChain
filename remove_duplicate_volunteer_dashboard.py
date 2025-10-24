#!/usr/bin/env python3
import re

# Read the file
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()

# Find the second volunteer_dashboard function and remove it
# Look for the pattern: @app.route("/volunteer_dashboard") followed by the function, then the next @app.route
pattern = r'(@app\.route\("/volunteer_dashboard"\)\s*def volunteer_dashboard\(\):.*?(?=@app\.route\("/volunteer_logout"\)))'

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

print("Duplicate volunteer_dashboard function removed")

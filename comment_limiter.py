#!/usr/bin/env python3
import re

# Read the file
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()

# Comment out @limiter.limit decorators
content = re.sub(r"(@limiter\.limit\([^)]+\))", r"# \1", content)

# Write back
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    "w",
    encoding="utf-8",
) as f:
    f.write(content)

print("Limiter decorators commented out")

#!/usr/bin/env python3
import re

# Read the file
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()

# Split into lines
lines = content.split("\n")

# Track seen routes
seen_routes = set()
new_lines = []
skip_until_next_route = False

for i, line in enumerate(lines):
    # Check if this is a route decorator
    route_match = re.match(r'@app\.route\("([^"]+)"', line.strip())
    if route_match:
        route = route_match.group(1)
        if route in seen_routes:
            # Skip this duplicate route and its function
            skip_until_next_route = True
            continue
        else:
            seen_routes.add(route)
            skip_until_next_route = False

    if skip_until_next_route:
        # Check if this is the start of a new route or function
        if re.match(r"@app\.route\(", line.strip()) or re.match(r"def ", line.strip()):
            skip_until_next_route = False
        else:
            continue

    new_lines.append(line)

# Join back
new_content = "\n".join(new_lines)

# Write back
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    "w",
    encoding="utf-8",
) as f:
    f.write(new_content)

print("Duplicate routes removed")

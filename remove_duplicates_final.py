#!/usr/bin/env python3

# Read the file
with open(
    "c:\\Users\\Stella Barbarella\\OneDrive\\Documents\\chatGPT\\Projet BG\\HelpChain\\backend\\appy.py",
    encoding="utf-8",
) as f:
    content = f.read()

# Split into lines
lines = content.split("\n")

# Track seen routes
seen_routes = set()
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Check if this is a route decorator
    import re

    route_match = re.match(r'@app\.route\("([^"]+)"', line.strip())
    if route_match:
        route = route_match.group(1)
        if route in seen_routes:
            # Skip this duplicate route and its function until next route or major comment
            while i < len(lines):
                line = lines[i]
                if re.match(r"@app\.route\(", line.strip()) or re.match(
                    r"# =====", line.strip()
                ):
                    break
                i += 1
            continue
        else:
            seen_routes.add(route)

    new_lines.append(line)
    i += 1

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

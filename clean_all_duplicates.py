def clean_duplicates():
    # Read the file
    with open("backend/appy.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Split into lines
    lines = content.split("\n")

    # Find all function definitions (lines starting with @app.route)
    route_lines = []
    for i, line in enumerate(lines):
        if line.strip().startswith("@app.route"):
            route_lines.append(i)

    print(f"Found {len(route_lines)} route decorators")

    # Group functions by their route path
    functions = {}
    i = 0
    while i < len(route_lines):
        start_line = route_lines[i]
        route_path = lines[start_line].strip()

        # Find the function definition (next non-decorator line)
        func_start = start_line
        while func_start < len(lines) and (
            lines[func_start].strip().startswith("@") or lines[func_start].strip() == ""
        ):
            func_start += 1

        if func_start < len(lines) and lines[func_start].strip().startswith("def "):
            func_name = lines[func_start].strip().split("(")[0].replace("def ", "")

            # Find the end of this function (next function definition or end of file)
            func_end = func_start + 1
            while func_end < len(lines):
                if lines[func_end].strip().startswith("def ") or lines[
                    func_end
                ].strip().startswith("@app.route"):
                    break
                func_end += 1

            # Store the function
            key = f"{route_path} -> {func_name}"
            if key not in functions:
                functions[key] = []
            functions[key].append((start_line, func_end))

        i += 1

    # Remove duplicates, keeping only the first occurrence
    lines_to_remove = set()
    for func_key, occurrences in functions.items():
        if len(occurrences) > 1:
            print(f"Function {func_key} has {len(occurrences)} duplicates")
            # Keep first occurrence, remove the rest
            for start_line, end_line in occurrences[1:]:
                for line_num in range(start_line, end_line):
                    lines_to_remove.add(line_num)

    # Create cleaned content
    cleaned_lines = []
    for i, line in enumerate(lines):
        if i not in lines_to_remove:
            cleaned_lines.append(line)

    cleaned_content = "\n".join(cleaned_lines)

    # Write back
    with open("backend/appy.py", "w", encoding="utf-8") as f:
        f.write(cleaned_content)

    print(f"Removed {len(lines_to_remove)} duplicate lines")
    print(
        f"Original file had {len(lines)} lines, cleaned file has {len(cleaned_lines)} lines"
    )


if __name__ == "__main__":
    clean_duplicates()

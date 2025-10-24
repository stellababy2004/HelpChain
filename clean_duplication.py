#!/usr/bin/env python3
import re


def clean_duplicated_functions():
    """Remove duplicated function definitions in appy.py"""

    # Read the file
    with open("backend/appy.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the first occurrence of admin_dashboard function
    admin_dashboard_pattern = r'@app\.route\("/admin_dashboard", endpoint="admin_dashboard"\)\s*@require_admin_login\s*def admin_dashboard\(\):.*?(?=@app\.route\("/profile")'

    # Find all matches
    matches = list(re.finditer(admin_dashboard_pattern, content, re.DOTALL))

    if len(matches) > 1:
        print(f"Found {len(matches)} admin_dashboard functions")

        # Keep only the first occurrence, remove the rest
        first_match = matches[0]
        # Find the end of the first function (before the next @app.route)
        end_pos = first_match.end()

        # Find the start of the second function
        second_match = matches[1]
        start_second = second_match.start()

        # Remove everything from start_second to the end of the duplicated content
        # We need to find where the duplication ends
        remaining_content = content[start_second:]

        # Find the next unique function after the duplication
        # Look for the first function that doesn't appear earlier
        lines = remaining_content.split("\n")
        unique_start = -1

        for i, line in enumerate(lines):
            if line.startswith('@app.route("/privacy")'):
                unique_start = i
                break

        if unique_start != -1:
            # Remove the duplicated content
            content_to_remove = remaining_content[
                : unique_start * len(lines[unique_start])
                + len("\n".join(lines[:unique_start]))
            ]

            # Clean content
            cleaned_content = (
                content[:start_second]
                + remaining_content[unique_start * len(lines[unique_start]) :]
            )

            # Write back
            with open("backend/appy.py", "w", encoding="utf-8") as f:
                f.write(cleaned_content)

            print("Duplicated functions removed successfully")
            return True
        else:
            print("Could not find unique content boundary")
            return False
    else:
        print("No duplicated admin_dashboard functions found")
        return False


if __name__ == "__main__":
    clean_duplicated_functions()

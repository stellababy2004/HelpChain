import re
import sys

VOID_TAGS = set(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)


def check(path):
    text = open(path, encoding="utf-8").read()
    tag_re = re.compile(r"<(/?)([a-zA-Z0-9\-]+)([^>]*)>", re.M)
    stack = []
    for m in tag_re.finditer(text):
        closing, tag, rest = m.group(1), m.group(2).lower(), m.group(3)
        pos = m.start()
        line = text.count("\n", 0, pos) + 1
        if closing:
            # end tag
            if not stack:
                print(f"Unexpected closing tag </{tag}> at line {line}")
                return 1
            # pop until matching tag
            if stack[-1] == tag:
                stack.pop()
            else:
                # try to find if tag exists earlier
                if tag in stack:
                    # pop until found
                    while stack and stack[-1] != tag:
                        popped = stack.pop()
                        print(f"Implied closing of <{popped}> before line {line}")
                    stack.pop()
                else:
                    print(
                        f"Unexpected closing tag </{tag}> at line {line} (no matching open)"
                    )
                    return 1
        else:
            # start tag
            # self-closing detection
            if rest.strip().endswith("/") or tag in VOID_TAGS:
                continue
            stack.append(tag)
    if stack:
        print("Unclosed tags at EOF:", stack)
        return 1
    print("No mismatched tags found")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: html_tag_check.py path")
        sys.exit(2)
    sys.exit(check(sys.argv[1]))

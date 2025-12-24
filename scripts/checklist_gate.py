#!/usr/bin/env python3
# scripts/checklist_gate.py
"""
Fail with exit code 1 if there is any [ ] Pending in PRODUCTION_DEPLOYMENT_CHECKLIST.md
"""
import sys
import re

def strip_fenced_code_blocks(text):
    # Remove all ```...``` fenced code blocks (multiline, any language)
    text = re.sub(r'```[\s\S]*?```', '', text, flags=re.MULTILINE)
    # Remove all inline code blocks `...` (single line)
    text = re.sub(r'`[^`]*`', '', text)
    return text

checklist = "PRODUCTION_DEPLOYMENT_CHECKLIST.md"
with open(checklist, encoding="utf-8") as f:
    content = f.read()

content_no_code = strip_fenced_code_blocks(content)

if "[ ]" in content_no_code:
    print("❌ There are still [ ] Pending items in the deployment checklist! Block production deploy.")
    sys.exit(1)
else:
    print("✅ All checklist items are marked as done. Proceeding with deploy.")
    sys.exit(0)

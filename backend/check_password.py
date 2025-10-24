#!/usr/bin/env python3
"""Check password hash"""

import os

from dotenv import load_dotenv
from werkzeug.security import check_password_hash

# Load .env from parent directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Check what password is expected
expected_password = os.getenv("ADMIN_PASSWORD", "Admin123")
print("Expected password from .env:", expected_password)

# Check if current hash matches
current_hash = "scrypt:32768:8:1$kM425pWE9abqe4QP$62c9d8fb6dcae048c0a1b9acdf9d581bd7a4c7db0d8498f74d03c64f2789f25177e3123ac836921285d3dade87dd34d82253e45ec5a19269ece96b9286fe9fe2"
print(
    "Current hash matches expected:",
    check_password_hash(current_hash, expected_password),
)
print("Current hash matches Admin123:", check_password_hash(current_hash, "Admin123"))

# Try to find what password was used
test_passwords = ["Admin123", "N!Zdx2!H%X#Icuyp", "admin123"]
for pwd in test_passwords:
    if check_password_hash(current_hash, pwd):
        print(f"Password match found: {pwd}")
        break
else:
    print("No password match found in test list")

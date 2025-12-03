from pathlib import Path

p = Path("tests/conftest.py").read_text(encoding="utf-8", errors="replace")
print("total try occurrences:", p.count("try:"))
print("total except occurrences:", p.count("except"))
lines = p.splitlines()
# find first except after a return admin_client occurrence
for i, line in enumerate(lines, 1):
    if 'return admin_client' in line:
        # show next 10 lines
        print('context after return admin_client at', i)
        for j in range(i+1, i+12):
            if j<=len(lines):
                print(j, lines[j-1])
        break
# show region 2025-2060
print('\n--- Lines 2025-2060 ---')
for i in range(2025, 2061):
    if i<=len(lines):
        print(i, repr(lines[i-1]))

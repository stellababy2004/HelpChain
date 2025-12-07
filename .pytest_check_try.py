from pathlib import Path
p=Path(r'c:\dev\HelpChain\HelpChain.bg\tests\conftest.py')
raw = p.read_bytes()
try:
    s = raw.decode('utf-8')
except Exception:
    s = raw.decode('latin-1', errors='ignore')
lines = s.splitlines()
stack = []
for i,l in enumerate(lines, start=1):
    stripped = l.lstrip()
    indent = len(l) - len(stripped)
    if stripped.startswith('try:'):
        stack.append((i, indent))
    if stripped.startswith('except') or stripped.startswith('finally'):
        for j in range(len(stack)-1, -1, -1):
            if stack[j][1] <= indent:
                stack.pop(j)
                break

if stack:
    print('Unmatched try(s):')
    for t in stack:
        print(t)
else:
    print('All try blocks matched with except/finally')
print('--- Last 40 lines around error area ---')
start = max(1, 1020)
for i in range(start, start+80):
    if i <= len(lines):
        print(f'{i:4d}: {lines[i-1]}')

p='c:\\dev\\HelpChain\\HelpChain.bg\\backend\\extensions.py'
with open(p,encoding='utf-8') as f:
    lines=f.readlines()
for i,l in enumerate(lines, start=1):
    if 180<=i<=220:
        print(f"{i:04d}: {l.rstrip()}")

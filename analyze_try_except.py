import re
p='c:/dev/HelpChain/HelpChain.bg/backend/extensions.py'
lines=open(p,'r',encoding='utf-8').read().splitlines()
stack=[]
for i,l in enumerate(lines, start=1):
    s=l.lstrip('\t ')
    indent=len(l)-len(s)
    if s.startswith('try:'):
        stack.append((i,indent))
    elif s.startswith('except') or s.startswith('finally'):
        # find latest try with same indent
        for j in range(len(stack)-1, -1, -1):
            if stack[j][1]==indent:
                stack.pop(j)
                break

print('remaining unmatched try blocks:')
for t in stack:
    print('line', t[0], 'indent', t[1], '->', lines[t[0]-1].strip())

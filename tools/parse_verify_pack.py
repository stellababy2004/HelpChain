#!/usr/bin/env python3
import re

def load_paths(all_objects_path='all_objects.txt'):
    m = {}
    try:
        with open(all_objects_path,'r',encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line:
                    continue
                parts=line.split(' ',1)
                h=parts[0]
                path = parts[1] if len(parts)>1 else ''
                if h not in m:
                    m[h]=path
    except FileNotFoundError:
        print(f'{all_objects_path} not found')
    return m

def main():
    paths = load_paths()
    entries = []
    try:
        with open('verify_pack_raw.txt','r',encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                m = re.match(r'^([0-9a-f]{40})\s+(\w+)\s+(\d+)\s+(\d+)\s+(\d+)', line)
                if m:
                    h = m.group(1)
                    t = m.group(2)
                    size = int(m.group(3))
                    if t == 'blob':
                        entries.append((size,h))
    except FileNotFoundError:
        print('verify_pack_raw.txt not found; run: git verify-pack -v .git/objects/pack/pack-*.idx > verify_pack_raw.txt')
        return
    entries.sort(reverse=True)
    with open('large_blobs_verify.txt','w',encoding='utf-8') as out:
        for size,h in entries[:200]:
            out.write(f"{size}\t{h}\t{paths.get(h,'')}\n")
    print('Wrote large_blobs_verify.txt')

if __name__=='__main__':
    main()

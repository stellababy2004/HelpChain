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
        pass
    return m


def main():
    paths = load_paths()
    entries = []
    try:
        with open('object_sizes_raw.txt','r',encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line.startswith('blob '):
                    continue
                parts=line.split()
                # format: blob <hash> <size>
                if len(parts) < 3:
                    continue
                h = parts[1]
                try:
                    size = int(parts[2])
                except:
                    continue
                entries.append((size,h))
    except FileNotFoundError:
        print('object_sizes_raw.txt not found')
        return
    entries.sort(reverse=True)
    with open('large_blobs_sorted.txt','w',encoding='utf-8') as out:
        for size,h in entries[:200]:
            out.write(f"{size}\t{h}\t{paths.get(h,'')}\n")
    print('Wrote large_blobs_sorted.txt')

if __name__=='__main__':
    main()

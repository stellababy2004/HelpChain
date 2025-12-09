#!/usr/bin/env python3
import subprocess
import sys


def git_cat_file_size(h):
    try:
        out = subprocess.check_output(["git","cat-file","-s",h])
        return int(out.strip())
    except Exception:
        return None

def main():
    objs = []
    try:
        with open('all_objects.txt',encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line:
                    continue
                parts = line.split(' ',1)
                h = parts[0]
                path = parts[1] if len(parts)>1 else ''
                size = git_cat_file_size(h)
                if size is None:
                    continue
                objs.append((size,h,path))
    except FileNotFoundError:
        print('all_objects.txt not found. Run: git rev-list --objects --all > all_objects.txt', file=sys.stderr)
        sys.exit(2)

    objs.sort(reverse=True, key=lambda x: x[0])
    with open('large_blobs.txt','w',encoding='utf-8') as out:
        for size,h,path in objs[:200]:
            out.write(f"{size}\t{h}\t{path}\n")
    print(f"Wrote large_blobs.txt with top {min(200, len(objs))} objects")

if __name__=='__main__':
    main()

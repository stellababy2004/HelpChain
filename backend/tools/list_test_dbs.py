import glob
import os
import tempfile

paths = glob.glob(os.path.join(tempfile.gettempdir(), '*_test.db'))
print('found', len(paths), 'test db files')
for p in paths:
    print(p)

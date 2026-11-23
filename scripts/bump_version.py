import re

# читаем текущую версию из buildozer.spec
with open('buildozer.spec', encoding='utf-8') as f:
    spec = f.read()

m = re.search(r'^version\s*=\s*([0-9.]+)', spec, re.M)
parts = m.group(1).split('.')
while len(parts) < 3:
    parts.append('0')
parts[2] = str(int(parts[2]) + 1)
new = '.'.join(parts)

spec = re.sub(r'^version\s*=.*$', 'version = ' + new, spec, count=1, flags=re.M)
with open('buildozer.spec', 'w', encoding='utf-8') as f:
    f.write(spec)

# синхронно обновляем APP_VERSION в main.py (кодовая метка (vX) сохраняется)
try:
    with open('main.py', encoding='utf-8') as f:
        main = f.read()
    main, n = re.subn(r'APP_VERSION = "[0-9.]+ $([^"]*)$"',
                      'APP_VERSION = "' + new + ' (\\1)"', main, count=1)
    if n:
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(main)
except FileNotFoundError:
    pass

print('new_version=' + new)

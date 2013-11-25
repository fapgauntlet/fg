# -*- mode: python -*-
a = Analysis(['fg.py'],
             pathex=['O:\\org\\prog\\fg'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
a.datas = [
    ('fg.py','fg.py', ''),
    ('setgifdelay.py', 'setgifdelay.py', ''),
    ('README.txt', 'README.txt', ''),
    ('BUGS.txt', 'BUGS.txt', ''),
    ('CHANGELOG.txt', 'CHANGELOG.txt', ''),
    ('LICENCE.txt', 'LICENCE.txt', ''),
]
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='fg.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False,
          icon='excellent.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='fg')

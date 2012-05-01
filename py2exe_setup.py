# usage: 
# - copy msvcp90.dll in this directory (it's in the exe dir)
# - python py2exe_setup.py py2exe

from distutils.core import setup
import py2exe

data_files = [
    'MSVCP90.dll',
    'fg.py',
    'setgifdelay.py',
    'py2exe_setup.py',
    'README.txt',
    'BUGS.txt',
    'CHANGELOG.txt',
]
setup(
        options={
            "py2exe": {
                "bundle_files": 2,
                "optimize": 2,
                "dist_dir": "fg-8",
                "compressed": True,
            }
        },
        console=['fg.py'], data_files=data_files
)


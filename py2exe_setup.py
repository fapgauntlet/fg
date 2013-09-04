# usage: 
# - copy msvcp90.dll in this directory (it's in the exe dir)
# - python py2exe_setup.py py2exe

from distutils.core import setup
import py2exe

data_files = [
    'msvcp90.dll',
    'msvcr90.dll',
    'gdiplus.dll',
    'msvcm90.dll',
    'fg.py',
    'setgifdelay.py',
    'py2exe_setup.py',
    'README.txt',
    'BUGS.txt',
    'CHANGELOG.txt',
]
setup(console=[{
		'script': 'fg.py',
		'icon_resources':[(1, 'excellent.ico')],
	}],
	data_files=data_files,
	options={
		"py2exe": {
			"bundle_files": 1,
			"optimize": 2,
			"dist_dir": "fg-8alpha2",
			"compressed": True,
		}
	},
)


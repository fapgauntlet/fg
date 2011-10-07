# build the exe with this script
# usage: 
# - copy msvcp90.dll in this directory (it's in the exe dir)
# - navigate to the directory in command line
# - python py2exe_setup.py py2exe
# - the dist directory contains the exe (and everything necessary)

from distutils.core import setup
import py2exe

data_files = ['MSVCP90.dll']
setup(
        options={
            "py2exe":{
                #"bundle_files":2,
                "optimize":2,
                "dist_dir":"dist_9",
                "compressed":True,
            }
        },
        console=['fg.py'], data_files=data_files
)

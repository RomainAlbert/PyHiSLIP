#!/usr/bin/env python
"""
Author:Noboru Yamamoto, KEK, Japan (c) 2009-2013

contact info: http://gofer.kek.jp/
or https://plus.google.com/i/xW1BWwWsj3s:2rbmfOGOM4c

Thanks to:
   Dr. Shuei Yamada(KEK, Japan) for improved vxi11scan.py

Revision Info:
$Author: noboru $
$Date: 2020-03-07 14:05:18 +0900 $ (isodatesec )
$HGdate: Sat, 07 Mar 2020 14:05:18 +0900 $
$Header: /Users/noboru/src/python/VXI11/PyVXI11-Current/setup.py,v f2bae8596f66 2020/03/07 05:05:18 noboru $
$Id: setup.py,v f2bae8596f66 2020/03/07 05:05:18 noboru $
$RCSfile: setup.py,v $
$Revision: f2bae8596f66 $
$Source: /Users/noboru/src/python/VXI11/PyVXI11-Current/setup.py,v $

change log:
2020/02/27 : add io_timeout parameters in write.
2020/02/27 : new tag. 1.15
"""
import os,platform,re,sys,os.path

from Cython.Distutils.extension import Extension
from Cython.Distutils import build_ext
from Cython.Build import cythonize

# python2/python3
extra=dict()

# if sys.version_info >= (3,):
#     extra['use_2to3'] = True
    
if sys.version_info >= (3,):
   PY3=True
else:
   PY3=False

try:
   from distutils.command.build_py import build_py_2to3 as build_py #for Python3
except ImportError:
   from distutils.command.build_py import build_py     # for Python2

from distutils.core import setup
#from distutils.extension import Extension

# macros managedd by mercurial keyword extension
#
HGTag="$HGTag: 1.15.33-f2bae8596f66 $"
HGdate="$HGdate: Sat, 07 Mar 2020 14:05:18 +0900 $" #(rfc822date)
#HGTagShort="$HGTagShort: 1.15.33 $"

#
HGcheckedin="$checked in by: Noboru Yamamoto <noboru.yamamoto@kek.jp> $"
#
# import hglib
# hgclient=hglib.open(".")
#
# #release = os.popen("hg log -r tip --template '{latesttag}.{latesttagdistance}-{node|short}'").read()
# release=HGTag
# #rev=HGTag[HGTag.index(":")+1:HGTag.index("-")].strip()
# rev=HGTagShort.strip()
#
rev="0.1"

sysname=platform.system()

if re.match("Darwin.*",sysname):
    RPCLIB=["rpcsvc"]
elif re.match("CYGWIN.*",sysname):
    RPCLIB=["rpc"]
else:
    RPCLIB=None

ext_modules=[]

ext_modules.append(Extension("cyHiSLIP", 
                             [
                               "pyhislip.pyx",
                             ] 
                             ,libraries=[]
                             ,depends=["pyhislip.pdx"]
                             ,language="c++"
                             ,cython_cplus=True
                             ,undef_macros=["CFLAGS"]
                             ,extra_compile_args=["-I/usr/include/tirpc"], # for Linux using tirpc lib.
))


## if you  like to compare cython version with swig-version, uncomment the 
## following lines. You must have swig in your path.
# ext_modules.append(Extension("_VXI11",["VXI11.i","VXI11_clnt.c","VXI11_xdr.c"]
#                     ,swig_opts=["-O","-nortti"]
#                     ,libraries=RPCLIB
#                     ))

ext_modules=cythonize( # generate .c files.
   ext_modules,
   compiler_directives={"language_level":"3" if PY3 else "2"}, # "2","3","3str"
)

setup(name="cyHiSLIP",
      version=rev,
      author="Noboru Yamamoto, KEK, JAPAN",
      author_email = "Noboru.YAMAMOTO@kek.jp",
      description='A Cython based Python module to control devices over HiSLIP protocol.',
      url="http://www-cont.j-parc.jp/",
      classifiers=['Programming Language :: Python',
                   'Programming Language :: Cython',
                   'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
                   ],
      ext_modules=ext_modules,
      cmdclass = {'build_ext': build_ext,
                  # 'build_py':build_py  # for 2to3 
      },
      py_modules=[
      ],
      **extra
)

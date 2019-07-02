
# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import distutils.sysconfig
import os
import sys
import numpy as np
from setuptools import setup, Extension
from Cython.Build import cythonize
from Cython.Distutils import build_ext

INCLUDE_DIRS = [np.get_include()]
# Add Cython OP extensions here
cython_op_exts = ['channel_value', 'measure', 'memory', 'utils']

# Add Cython QuTiP extensions here
cython_qutip_exts = ['graph_utils', 'math', 'ptrace', 'sparse_utils',
                     'spconvert', 'spmatfuncs', 'spmath']

# Extra link args
_link_flags = []
# If on Win and Python version >= 3.5 and not in MSYS2 (i.e. Visual studio compile)
if (sys.platform == 'win32' and int(str(sys.version_info[0])+str(sys.version_info[1])) >= 35
        and os.environ.get('MSYSTEM') is None):
    _compiler_flags = []
# Everything else
else:
    _compiler_flags = ['-O2', '-funroll-loops']
    if sys.platform == 'darwin':
        # These are needed for compiling on OSX 10.14+
        _compiler_flags.append('-mmacosx-version-min=10.9')
        _link_flags.append('-mmacosx-version-min=10.9')

# Remove -Wstrict-prototypes from cflags
cfg_vars = distutils.sysconfig.get_config_vars()
if "CFLAGS" in cfg_vars:
    cfg_vars["CFLAGS"] = cfg_vars["CFLAGS"].replace("-Wstrict-prototypes", "")


EXT_MODULES = []
# Add Cython files from cy
for ext in cython_op_exts:
    _mod = Extension("cy."+ext,
                     sources=['cy/'+ext+'.pyx'],
                     include_dirs=[np.get_include()],
                     extra_compile_args=_compiler_flags,
                     extra_link_args=_link_flags,
                     language='c++')
    EXT_MODULES.append(_mod)

# Add Cython files from qutip_lite/cy
for ext in cython_qutip_exts:
    _mod = Extension("qutip_lite.cy."+ext,
                     sources=['qutip_lite/cy/'+ext+'.pyx'],
                     include_dirs=[np.get_include()],
                     extra_compile_args=_compiler_flags,
                     extra_link_args=_link_flags,
                     language='c++')
    EXT_MODULES.append(_mod)


setup(name='OpenPulse',
      ext_modules=cythonize(EXT_MODULES)
     )
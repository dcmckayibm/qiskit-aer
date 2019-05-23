# -*- coding: utf-8 -*-

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

# This file is part of QuTiP: Quantum Toolbox in Python.
#
#    Copyright (c) 2011 and later, Paul D. Nation and Robert J. Johansson.
#    All rights reserved.

import os
import sys
import numpy as np
import qutip as qt
import openpulse.solver.settings as op_set

_cython_path = os.path.abspath(qt.cy.__file__).replace('__init__.py', '')
_cython_path = _cython_path.replace("\\", "/")
_include_string = "'"+_cython_path+"complex_math.pxi'"


class OPCodegen(object):
    """
    Class for generating cython code files at runtime.
    """
    def __init__(self, op_system):

        sys.path.append(os.getcwd())

        # Hamiltonian time-depdendent pieces
        self.op_system = op_system
        self.dt = op_system.dt

        self.num_ham_terms = len(self.op_system.system)
        
        # Code generator properties
        self._file = None
        self.code = []  # strings to be written to file
        self.level = 0  # indent level
        self.spline_count = 0

    def write(self, string):
        """write lines of code to self.code"""
        self.code.append("    " * self.level + string + "\n")

    def file(self, filename):
        """open file called filename for writing"""
        self._file = open(filename, "w")

    def generate(self, filename="rhs.pyx"):
        """generate the file"""

        for line in cython_preamble():
            self.write(line)

        # write function for Hamiltonian terms (there is always at least one
        # term)
        for line in cython_checks() + self.ODE_func_header():
            self.write(line)
        self.indent()
        for line in func_header(self.op_system):
            self.write(line)
        for line in self.channels():
            self.write(line)
        for line in self.func_vars():
            self.write(line)
        for line in self.func_end():
            self.write(line)
        self.dedent()

        self.file(filename)
        self._file.writelines(self.code)
        self._file.close()
        op_set.CGEN_NUM += 1

    def indent(self):
        """increase indention level by one"""
        self.level += 1

    def dedent(self):
        """decrease indention level by one"""
        if self.level == 0:
            raise SyntaxError("Error in code generator")
        self.level -= 1

    def ODE_func_header(self):
        """Creates function header for time-dependent ODE RHS."""
        func_name = "def cy_td_ode_rhs("
        # strings for time and vector variables
        input_vars = ("\n        double t" +
                      ",\n        complex[::1] vec")
        for k in range(self.num_ham_terms):
            input_vars += (",\n        " +
                           "complex[::1] data%d, " % k +
                           "int[::1] idx%d, " % k +
                           "int[::1] ptr%d" % k)
            
        #Add global vaiables
        input_vars += (",\n        " + "complex[::1] pulse_array")
        input_vars += (",\n        " + "unsigned int[::1] pulse_indices")

        #Add per experiment variables
        for key in self.op_system.channels.keys():
            input_vars += (",\n        " + "double[::1] %s_pulses" % key)
            input_vars += (",\n        " + "double[::1] %s_fc" % key)

        # add Hamiltonian variables
        for key in self.op_system.vars.keys():
            input_vars += (",\n        " + "complex %s" % key)
        
        # register
        input_vars += (",\n        " + "unsigned char[::1] register")
            
        func_end = "):"
        return [func_name + input_vars + func_end]

    
    def channels(self):
        """Write out the channels
        """
        channel_lines = [""]

        channel_lines.append("# Compute complex channel values at time `t`")
        for chan, idx in self.op_system.channels.items():
            chan_str = "%s = channel_value(t, %s, " %(chan, idx) + \
                       "%s_pulses,  pulse_array, pulse_indices, " % chan + \
                       "%s_fc, register)" % chan
            channel_lines.append(chan_str)
        channel_lines.append('')
        return channel_lines
    
    
    def func_vars(self):
        """Writes the variables and spmv parts"""
        func_vars = []

        func_vars.append("# Eval the time-dependent terms and do SPMV.")
        for idx, term in enumerate(self.op_system.system):
            if isinstance(term, list) or term[1]:
                func_vars.append("td%s = %s" % (idx, term[1]))
                func_vars.append("if abs(td%s) > 1e-15:" % idx)
                
                spmv_str = "spmvpy(&data{i}[0], &idx{i}[0], &ptr{i}[0], "+ \
                           "&vec[0], td{i}, &out[0], num_rows)"
                func_vars.append("    "+spmv_str.format(i=idx))

            else:
                spmv_str = "spmvpy(&data{i}[0], &idx{i}[0], &ptr{i}[0], "+ \
                           "&vec[0], 1.0, &out[0], num_rows)"
                func_vars.append(spmv_str.format(i=idx))


        return func_vars

    def func_end(self):
        end_str = [""]
        end_str.append("# Convert to NumPy array, grab ownership, and return.")
        end_str.append("cdef np.npy_intp dims = num_rows")
        
        temp_str = "cdef np.ndarray[complex, ndim=1, mode='c'] arr_out = "
        temp_str += "np.PyArray_SimpleNewFromData(1, &dims, np.NPY_COMPLEX128, out)"
        end_str.append(temp_str)
        end_str.append("PyArray_ENABLEFLAGS(arr_out, np.NPY_OWNDATA)")
        end_str.append("return arr_out")
        return end_str 

def func_header(op_system):
    func_vars = ["", 'cdef size_t row', 'cdef unsigned int num_rows = vec.shape[0]',
                     "cdef double complex * " +
                     'out = <complex *>PyDataMem_NEW_ZEROED(num_rows,sizeof(complex))'
                ]
    func_vars.append("")

    for val in op_system.channels:
        func_vars.append("cdef double complex %s" % val)

    for kk, item in enumerate(op_system.system):
        if item[1]:
            func_vars.append("cdef double complex td%s" % kk)

    return func_vars

def cython_preamble():
    """
    Returns list of code segments for Cython preamble.
    """
    preamble = ["""\
#!python
#cython: language_level=3
# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np
cimport numpy as np
cimport cython
np.import_array()
cdef extern from "numpy/arrayobject.h" nogil:
    void PyDataMem_NEW_ZEROED(size_t size, size_t elsize)
    void PyArray_ENABLEFLAGS(np.ndarray arr, int flags)

from qutip.cy.spmatfuncs cimport spmvpy
from qutip.cy.math cimport erf
from libc.math cimport pi

from openpulse.cython.channel_value cimport channel_value

include """+_include_string+"""
"""]
    return preamble


def cython_checks():
    """
    List of strings that turn off Cython checks.
    """
    return ["""@cython.cdivision(True)
@cython.boundscheck(False)
@cython.wraparound(False)"""]

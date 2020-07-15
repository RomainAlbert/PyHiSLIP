#!cython
# distutils: language=c++
# -*- coding: utf-8 -*-

# to avoid undefined "__pyx_ctuple_int__and_long" type error
# you need this for python2
ctypedef (int, int) int_int_tuple
# but for python3 you need this
ctypedef (int, long) int_long_tuple




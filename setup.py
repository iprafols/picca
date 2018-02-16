#!/usr/bin/env python

import glob

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

scripts = glob.glob('bin/*')

description = "Package for Igm Cosmological-Correlations Analyses"

version="0.9"
setup(name="picca",
      version=version,
      description=description,
      url="https://github.com/igmhub/picca",
      author="Nicolas Busca et al",
      author_email="ngbusca@lpnhe.in2p3.fr",
      packages=['picca'],
      package_dir = {'': 'py'},
      install_requires=['scipy','numpy','iminuit','fitsio','healpy','numba','future'],
      test_suite='picca.test.test_cor',
      scripts = scripts
      )


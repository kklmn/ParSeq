# -*- coding: utf-8 -*-
from setuptools import setup

# get it from parseq/help/top.rst, change imagezoom:: to image::
long_description = r"""
ParSeq
======

Package ParSeq is a python software library for **Par**\ allel execution of
**Seq**\ uential data analysis. It implements a general analysis framework that
consists of transformation nodes -- intermediate stops along the data pipeline
to visualize data, display status and provide user input -- and transformations
that connect the nodes. It provides an adjustable data model (supports
grouping, renaming, moving and drag-and-drop), tunable data format definitions,
plotters for 1D, 2D and 3D data, cross-data analysis routines and flexible
widget work space suitable for single- and multi-screen computers. It also
defines a structure to implement particular analysis pipelines as relatively
lightweight Python packages.

ParSeq is intended for synchrotron based techniques, first of all spectroscopy.

Main features
-------------

-  ParSeq allows creating analysis pipelines as lightweight modules.

-  Flexible use of screen area by detachable/dockable transformation nodes
   (parts of analysis pipeline).

-  Two ways of acting from GUI onto multiple data: (a) simultaneous work with
   multiply selected data and (b) copying a specific parameter or a group of
   parameters from active data items to later selected data items.

-  Undo and redo for most of treatment steps.

-  Entering into the analysis pipeline at any node, not only at the head of the
   pipeline.

-  Creation of cross-data combinations (e.g. averaging, RMS or PCA) and their
   propagation downstream the pipeline together with the parental data. The
   possibility of termination of the parental data at any selected downstream
   node.

-  Parallel execution of data analysis with multiprocessing or multithreading
   (can be opted by the pipeline application).

-  Informative error handling that provides alerts and stack traceback -- the
   type and location of the occurred error.

-  Export of the workflow into a project file. Export of data into various data
   formats with accompanied Python scripts that visualize the exported data for
   the user to tune their publication plots.

-  ParSeq understands container files (presently only hdf5) and adds them to
   the system file tree as subfolders. The file tree, including hdf5
   containers, is lazy loaded thus enabling big data collections.

-  A web viewer widget near each analysis widget displays help pages generated
   from the analysis widget doc strings. The help pages are built by Sphinx at
   the startup time.

-  The pipeline can be operated via scripts or GUI.

The mechanisms for creating nodes and transformations, connecting them together
and creating Qt widgets for the transformations are exemplified by separately
installed analysis packages:

- `ParSeq-XES-scan <https://github.com/kklmn/ParSeq-XES-scan>`_
- `ParSeq-XES-dispersive <https://github.com/kklmn/ParSeq-XES-dispersive>`_
- `ParSeq-XAS <https://github.com/kklmn/ParSeq-XAS>`_

Dependencies
------------

- `silx <https://github.com/silx-kit/silx>`_ -- for plotting and Qt imports
- `sphinx <https://github.com/sphinx-doc/sphinx>`_ -- for building html documentation

Launch an example
-----------------

Either install ParSeq and a ParSeq pipeline application by their installers to
the standard location or put them to any folder in their respective folders
(``parseq`` and e.g. ``parseq_XES_scan``) and run the ``*_start.py`` module of
the pipeline. You can try it with ``--help`` to explore the available options.
An assumed usage pattern is to load a project ``.pspj`` file from GUI or from
the starting command line.

Hosting and contact
-------------------

The ParSeq project is hosted on `GitHub <https://github.com/kklmn/ParSeq>`_.
Please use the project’s Issues tab to get help or report an issue.
"""

setup(
    name='parseq',
    version='0.9.91',
    description='ParSeq is a python software library for Parallel execution of'
                ' Sequential data analysis.',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    author='Konstantin Klementiev',
    author_email='konstantin.klementiev@gmail.com',
    url='http://parseq.readthedocs.io',
    project_urls={'Source': 'https://github.com/kklmn/ParSeq'},
    platforms='OS Independent',
    license='MIT License',
    keywords='data-analysis pipeline framework gui synchrotron spectroscopy',
    # python_requires=,
    zip_safe=False,  # True: build zipped egg, False: unzipped
    packages=['parseq',
              'parseq.core',
              'parseq.gui',
              'parseq.help',
              'parseq.tests', 'parseq.third_party', 'parseq.utils'],
    # package_dir={'parseq': '.'},
    package_data={
        'parseq': ['CODERULES.txt'],
        'parseq.gui': ['_images/*.*'],
        'parseq.help': [
            '*.rst', '*.bat',
            '_images/*.*', '_static/*.*', '_templates/*.*', 'exts/*.*',
            '_themes/*/*.*', 'help/_themes/*/*/*.*'],
        'parseq.tests': ['*.png'],
        },
    install_requires=['numpy>=1.8.0', 'scipy>=0.17.0', 'matplotlib>=2.0.0',
                      'sphinx>=1.6.2', 'sphinxcontrib-jquery', 'autopep8',
                      'h5py', 'silx>=1.1.0', 'hdf5plugin', 'psutil'],
    classifiers=['Development Status :: 5 - Production/Stable',
                 'Intended Audience :: Science/Research',
                 'Natural Language :: English',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'License :: OSI Approved :: MIT License',
                 'Intended Audience :: Science/Research',
                 'Topic :: Scientific/Engineering',
                 'Topic :: Software Development',
                 'Topic :: Software Development :: User Interfaces']
    )

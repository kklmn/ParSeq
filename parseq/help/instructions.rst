.. _instructions:

Detailed installation instructions
----------------------------------

Get Python
~~~~~~~~~~

`WinPython <https://sourceforge.net/projects/winpython/files>`_ is the easiest
way to get Python on Windows. It is portable (movable) and one can have many
WinPython installations without mutual interference.

`Anaconda <https://www.anaconda.com/download>`_ is another popular Python
distribution. It works on Linux, MacOS and Windows.

Automatic installation of ParSeq
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    pip install parseq

or::

    conda install conda-forge::parseq

Running ParSeq without installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Because ParSeq does not build anything at the installation time, it can be used
*without installation*, only its source code is required. One advantage of no
installation is a single location of ParSeq served by all, possibly many, Python
installations; that location can even span various OS's if it is on a network
drive. Get ParSeq as a zip from GitHub and unzip it to a suitable location.

For running ParSeq without installation, all required dependencies must be
installed beforehand. Look into ParSeq's `setup.py` and find those dependencies
in the list `install_requires`, they are pip installable.

::

    pip install sphinxcontrib-jquery autopep8 h5py hdf5plugin silx psutil pyqtwebengine docutils distro colorama sphinx_tabs siphash24

A typical pitfall in this scenario is the presence of ParSeq at multiple
locations. To discover which ParSeq package is actually in use, start a Python
session, import parseq and examine its `parseq.__file__`.

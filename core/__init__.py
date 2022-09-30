# -*- coding: utf-8 -*-
u"""
Create analysis pipeline
========================

Consider `parseq_XES_scan` as an example for the development steps described
below.

Basic concepts and ideas
------------------------

An analysis pipeline consists of data nodes and transformations that connect
the nodes. Data nodes define array names that will appear as attributes of data
objects, e.g as ``item.x``, with ``x`` being an attribute of a data object
``item``. The array values will be read from files or calculated from other
arrays. The pipeline can be used with or without GUI widgets. In the former
case, the defined node arrays will appear in the node plotting: 1D, 2D or 3D
(a stack of 2D plots).

Each transformation class defines a dictionary of transformation parameters and
default values for them. It also defines a static method that calculates data
arrays. The parameters will be attributed to each data object. The parameter
values are supposed to be changed in user supplied GUI widgets. This change can
be done simultaneously for one or several active data objects. Alternatively,
any parameter can be copied to one or several later selected data.

Each transformation can optionally define the number of threads or processes
that will start in parallel and run the transformation of several data items.
The multiprocessing python API requires the main transformation method as a
*static* method (not an instance method). Additionally, for the sake of
multiprocessing, all input and output arrays have to be added to ``inArrays``
and ``outArrays`` lists (attributes of the transformation class).

In the user-supplied GUI widgets, one for each data node, all interactive GUI
elements should get registered using a few dedicated methods. The registration
will enable automatic GUI update from the active data and will run
transformations given the updated parameters, so no
`signal slots <https://doc.qt.io/qt-6/signalsandslots.html>`_
are typically required. The registration will also enable copying
transformation parameters to other data by means of popup menus on each GUI
element.

The data model is a single object throughout the pipeline. Data can be
rearranged by the user: ordered, renamed, grouped and removed. The data model
tree is present in *each* data node, not as a single tree instance, with the
idea also to serve as a plot legend that should always be close to the plot.
User selection in the data model is common for all transformation nodes. For 1D
data, the line color is the same in all data nodes. 1D data plotting can
optionally be done for dynamically (via mouse selection) or statically (via
check boxes) selected data. 2D and 3D data plotting is always done for one
selected data object.

The transformation class docstrings will be built by ParSeq using `Sphinx
<https://www.sphinx-doc.org>`_ into an html file and will be displayed in a
help panel close to the transformation widget.

Prepare pipeline metadata and images
------------------------------------

Create a project directory for the pipeline. Create `__init__.py` file that
defines metadata about the project. Note that user pipeline applications and
ParSeq itself use the module `parseq.core.singletons` as a means to store
global variables; the pipeline’s `__init__.py` module defines a few of them.
Together with the docstrings of the module, these metadata will appear in the
About dialog.

Create `doc/_images` directory and put an application icon there. The pipeline
transformations will have class docstrings that may also include images; those
images should be located here, in `doc/_images`.

Make data nodes
---------------

To define a node class means to name all necessary arrays, define their roles,
labels and units.

Make data transformations
-------------------------

Start making a transformation class with defining a dictionary `defaultParams`
of default parameter values. Decide on using multiprocessing/multithreading by
specifying `nThreads` or `nProcesses`. If any of these numbers is > 1 (the
default values are both 1), specify two lists of array names: `inArrays` and
`outArrays`. Define a static method :meth:`.Transform.run_main`. Note, it can
have a few signatures. Within the method, get the actual transformation
parameters from the dictionary `data.transformParams` and the defined data
arrays as attributes of `data`, e.g. ``data.x``.

For expensive transformations, you should update the *progress* status.

For accessing arrays of other data objects, use a different signature of
:meth:`.Transform.run_main`, note that in this case multiprocessing is not
possible.

Make GUI widgets
----------------

The widgets that control transformation parameters are descendants of
:class:`.PropWidget`. The main methods of that class are
:meth:`.PropWidget.registerPropWidget` and
:meth:`.PropWidget.registerPropGroup`. They use the Qt signal/slot mechanism to
update the corresponding transformation parameters; the user does not have to
explicitly implement the reaction slots. Additionally, these methods enable
copying transformation parameters to other data by means of popup menus, update
the GUI upon selecting data objects in the data tree, start the corresponding
transformation and operate undo and redo lists.

Because each transformation already has a set of default parameter values,
these GUI widgets can gradually grow during the development time, without
compromising the data pipeline functionality.

Provide docstrings in reStructuredText markup, they will be built by Sphinx and
displayed near the corresponding widgets.

Make data pipeline
------------------

This is a small module that instantiates the above nodes, transformations and
widgets and connects them together.

Create test data tree
---------------------

Put a few data files in a local folder (i.e. `data`) and create a module that
defines a function that loads the data into a :ref:`data tree <data>`, defines
suitable transformation parameters and launches the first transformation (the
next ones will start automatically).

Create pipeline starter
-----------------------

The starter should understand command line arguments and prepare options for
loading the test data and to run the pipeline with and without GUI.

Creating development versions of analysis application
-----------------------------------------------------

Copy the whole folder of the application to the same level but with a different
name, e.g. append a version suffix. In the import section in the start script
change the import name to the above created folder name. Done.

"""

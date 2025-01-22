# -*- coding: utf-8 -*-
u"""
Create analysis pipeline
========================

Consider `parseq_XES_scan` and `parseq_XAS` as examples for the development
steps described below.

Centralized facilities
----------------------

Nodes and transformations
~~~~~~~~~~~~~~~~~~~~~~~~~

.. imagezoom:: _images/pipeline-graph-XAS.png
   :align: right
   :alt: &ensp;A pipeline for data processing of XAS spectra. This pipeline has
       multiple entry nodes and three fitting routines. It partially operates
       in multithreading and multiprocessing.

Analysis pipeline is a chain of data transformations with a set of intermediate
stops -- nodes -- where the results can be visualized and assessed and the
transformations can be steered. See an example on the right.

Data nodes define array names that will appear as attributes of data objects.
The array values will be read from files or calculated from other arrays. The
pipeline can be used with or without GUI widgets. In the former case, the
defined node arrays will appear in the node plot: 1D, 2D or 3D (a stack of 2D
plots).

.. imagezoom:: _images/pipeline-data-tree.png
   :alt: &ensp;EXAFS spectra arranged in a tree. The item tooltips present data
       flow information, array sizes and error messages.

The data tree model (as in the Qt's `Model/View Programming
<https://doc.qt.io/qt-6/model-view-programming.html>`_ concept) is a single
object throughout the pipeline. In contrast, data tree widgets, see an example
on the left, are present in *each* data node, not as a single tree instance,
with the idea to also serve as a plot legend. The data tree can be populated
from the file tree by using the popup menu or by a drag-and-drop action. The
newly loaded data get their set of transformation parameters from the currently
active data item (or the first of them if several items were active). If no
items have been previously loaded, the parameters are read from the ini file.
If the ini file does not exist yet, the parameters get their values from
`defaultParams` dictionary defined in each transformation class.

Data can be rearranged by the user: ordered, renamed, grouped and removed. User
selection in the data model is common for all transformation nodes. For 1D data
the line color is the same in all data nodes. 1D data plotting can optionally
be done for several curves simultaneously: for those selected either
dynamically (via mouse selection) or statically (via check boxes). This
behavior is set by clicking on the header of the visibility column: it toggles
between the icon with one eye or many eyes. 2D and 3D data plotting is always
done for one selected data object -- the first one among selected data items.

Each transformation class defines a dictionary of transformation parameters and
default values for them. It also defines a static method that calculates data
arrays. The transformation parameters are attributed to each data object. The
parameter values are supposed to be changed in GUI widgets. This change can be
done simultaneously for one or several active data objects. Alternatively, any
parameter can be copied to one or several later selected data.

.. imagezoom:: _images/pipeline-transform-apply.png
   :align: right
   :alt: &ensp;An example of the apply/reset popup menu on a control element.

Each transformation can optionally define the number of threads or processes
that will start in parallel to run the transformation of several data items.
The multiprocessing python API requires the main transformation method as a
*static* or *class* method (not an instance method). Additionally, for the sake
of inter-process data transfer in multiprocessing, all input and output node
arrays have to be added to ``inArrays`` and ``outArrays`` lists (attributes of
the transformation class).

In the pipeline GUI widgets, all interactive GUI elements can be registered
using a few dedicated methods of the base class :class:`PropWidget`. The
registration will enable (a) automatic GUI update from the active data and will
run transformations given the updated GUI elements, so no
`signal slots <https://doc.qt.io/qt-6/signalsandslots.html>`_
are typically required. The registration will also enable (b) copying
transformation parameters to other data by means of popup menus on each GUI
element, see on the right.

Docked node widgets
~~~~~~~~~~~~~~~~~~~

With the idea of flexible usage of screen area, the node widgets were made
detachable and dockable into the main ParSeq window. To do this, drag a node
widget by its caption bar. To dock it back, hover it over the main window or
use the dock button at the right end of the caption bar.

The state of each node widget (docked or floating) and its floating geometry is
saved in ini file and project files.

Undo and redo
~~~~~~~~~~~~~

.. imagezoom:: _images/pipeline-undo.png
   :align: left
   :alt: &ensp;The undo menu where individual actions can be reverted or
       deleted. The most typical way of using undo is to sequentially reverse
       actions from the top of the undo stack, either by the Undo button or the
       standard key combination Ctrl+Z.

The change of any transformation parameter can be reverted or redone again by
using undo/redo actions. Adding or deleting data items can also be reverted.
Parseq will keep reference to the deleted data items. In order to free up RAM
from the deleted items, the undo or redo list can manually be emptied.

File tree views and file formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each transformation node has its own file tree view with a data format widget
at its bottom. The file tree is by default visible only in the pipeline head
node(s). It can be made visible/hidden by the vertical button of the leftmost
splitter widget "files & containers".

The file tree model is a joint model of the standard Qt's `QFileSystemModel`
and the silx's `Hdf5TreeModel`, which means that hdf5 files are displayed in
the same file tree as subdirectories.

When an entry in the data tree is clicked, the corresponding file or hdf5 entry
gets highlighted in the starting transformation node widget. When the file tree
is browsed, the highlight color is green if this entry can be loaded, i.e. the
data format fields in the data format widget are defined and valid.

.. imagezoom:: _images/pipeline-file-tree.png
   :align: right
   :alt: &ensp;The file tree of a node. Visible is an expanded entry of an hdf5
       file. The sum of the two selected arrays will define I0 array.

ParSeq works with two file types: column text files and hdf5 files.

For column files, the format definitions are expressions of variables `Col0`,
`Col1` etc, e.g. as `Col3+Col4`. The expressions may include numpy functions:
`np.log(Col6/Col7)`. The file header can optionally be defined by the number of
header lines, by the leading comment character or a key word present in the
last header line. The whole header will serve as metadata for the corresponding
data item.

For hdf5 files, the format definitions are relative hdf5 paths or expressions
of a data dictionary `d`, whose keys are relative hdf5 paths:
`d["measurement/albaem-01_ch1"] + d["measurement/albaem-01_ch2"]`. The easiest
way to build these expressions is to use the popup menu in the file tree view,
see the image on the right. String or scalar hdf5 entries can be inserted into
the list of metadata items, again by using the popup menu. Note that you can
use hdf5 data sets from various hdf5 data groups or even hdf5 data files, not
necessarily from one data group when you load one data item.

The format definitions will be restored at the next program start. The data
format widget updates upon data selection change. So if several data formats
are in use in one session, the selection of a right data item is a way to
activate the right data format before loading the next similar data item.
The format definitions can also be saved into an ini file (.parseq/formats.ini)
and later restored from it using the popup menu when right-clicked on a data
file.

Automatic data loading can be activated by the check box "auto load new data
from current location", which is a useful feature during beam times.

Metadata
~~~~~~~~

Metadata widget joins the metadata string variables, see the previous section.
The widget can also be used to examine text files for column positions, use the
popup menu in the file tree view for that. The widget is hidden by default and
is located below the node plot.

Plots
~~~~~

.. imagezoom:: _images/pipeline-line-props.png
   :align: right
   :alt: &ensp;Line properties accessed from the header of a node's data tree.

The node plots are used to display data and to host a few analysis widgets:
regions of interest (ROIs) and data correction widgets. The 1D, 2D and 3D (2D
stacks) plots are adopted from silx with a few customizations.

Bear in mind that if several items have the same alias, silx displays only one
of them, so make sure aliases are unique. Parseq will try to append a numbered
suffix to the alias if the added data have the same file name. Aliases can
always be changed by the user.

In 1D plotting window, clicking on a curve will select the corresponding data
item in the data tree widget. Auxiliary curves can be added in user-defined
transformation widgets by specifying a method `extraPlot()`. The curves should
have their `legend` property defined in the following format: the data item
alias followed by a dot followed by a sub-name. If this convention is followed,
the curves become clickable, which will select the corresponding data item in
the data tree. Selected data items are plotted on top of the others.

Default plot settings for 1D curves can be set in the definitions of node
arrays. The GUI can also change it from any data tree view, see on the right.

The silx's plots may define a plot *backend*. Currently silx implements
'matplotlib' and 'opengl'. The former one is default in ParSeq as it looks
better in almost all scenarios, the latter one is quicker, especially for 2D
and 3D plots. The user is free to select either backend by CLI parameters of
the pipeline starter.

Fits
~~~~

Data nodes can optionally host curve fitting routines. If one or more fit
widgets were specified for a given node, they appear in separate splitters
under the node's plot. In the initial view, the splitters are collapsed.

.. imagezoom:: _images/pipeline-fit-EXAFS.png
   :align: right
   :alt: &ensp;EXAFS fit widget as an example of ParSeq fit widgets. It was
       built on top of the ParSeq base fit and base fit widget classes.

Similarly to transformations, fitting solvers can run in parallel for several
data items. Fitting parameters can be constrained or tied to other parameters,
also to parameters of another data item fit. See an example fit widget on the
right.

ParSeq implements a base fit class :class:`parseq.fits.basefit.Fit` and its
widget mate :class:`parseq.gui.fits.gbasefit.FitWidget`. These are parent
classes for ParSeq's Liner Combination Fit, Function Fit and EXAFS Fit.

The actual fit worker for each fit process or thread is
`scipy.optimize.curve_fit
<https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html>`_.
Its performance figures are displayed at the bottom of each fit widget.

Cross-data combinations
~~~~~~~~~~~~~~~~~~~~~~~

Data of equal shapes can be combined to produce joint secondary data: average,
sum, rms deviation and PCA components (to appear in a next release). The
current implementation asserts equal shapes and averages the abscissas of the
contributing data. Interpolation options will be added in later releases.

Whenever the contributing data have been modified in an upstream
transformation, the combined data will also update.

Standard data corrections
~~~~~~~~~~~~~~~~~~~~~~~~~

ParSeq data pipelines perform data evolution in specialized *transformations*.
ParSeq also implements a few standard data *corrections*, intended for
amendment of experimental 1D data curves. These include (a) range deletion,
(b) range vertical scaling, (c) replacement by a spline and (d) a step
correction.

Although data can flow in ParSeq without GUIs, data corrections are most
conveniently done using the mouse.

Project saving with data export and plot script generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. imagezoom:: _images/pipeline-proj-load.png
   :align: left
   :alt: &ensp;The Load project dialog. In the right panel is an image browser
       of the project plots.

.. imagezoom:: _images/pipeline-proj-save.png
   :align: right
   :alt: &ensp;The Save project dialog. The bottom panel is a widget for data
       export options.

There are a few example projects files coming with each pipeline application.
A ParSeq project file (.pspj) defines the data tree and all parameters for all
transformations and fits. It has an `ini file structure
<https://docs.python.org/3/library/configparser.html>`_. At its saving time
ParSeq also saves all relevant plot views that can be browsed in the Load
project dialog, see on the left.

Before starting the Save project dialog, select the data items to be exported.
In the dialog, select the nodes to export from, data format(s) and whether a
plotting script is wanted. The script will plot the *exported data* and
preserve the plotting settings from the analysis pipeline. The idea of the
script generation is twofold: to demonstrate the access to the saved data and
to give a possibility to tune the resulting figures. The scripts have a few
comments inside about tuning axis ranges, axis labels and curve legends.

In the saved project, file path to each data item is saved in two versions: as
an absolute path and as a relative path in respect to the project location.
When the project is copied together with the files to a new location, the
project should be directly loadable. When copied from a GPFS location at a
beamline, this may not work, and the relative paths have to be manually edited
by a Search/Replace operation in a text file editor.

Error handling
~~~~~~~~~~~~~~

Should an error occur during a transformation, this error is caught by ParSeq.
The corresponding data item turns to a bad state displayed by a red background
in the data tree. The caught error is displayed in the tooltip of that data
tree item where it names the transformation, the data item and the involved
python module. The error can be copied to clipboard.

Additionally, errors are written to the pipeline log file. The log file is
located in the user's home directory in ".parseq" subfolder. Note, the log file
is limited to one program session; it renewed at the next program start. The
logging level depends on the verbosity settings set by the command-line
options.

Command-line interface and start options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The available command line options of the starter script can be revealed with a
:command:`--help` key. Most of them are intended for development purpose.

Performance profiling
~~~~~~~~~~~~~~~~~~~~~

If the starter script is started with an elevated verbosity level (e.g. with a
key :command:`--verbosity 100`), the terminal output prints the timing results
for each relevant invocation of transformation and plotting methods, see below.
This functionality is meant as a tool for data pipeline development.

.. imagezoom:: _images/pipeline-timing.png
   :align: none
   :alt: &ensp;An example of the terminal output with timing figures, enabled
       by the CLI option `--verbosity` (*or* `-v`).

Help system
~~~~~~~~~~~

The transformation class docstrings are built by ParSeq at the application
start up time using `Sphinx <https://www.sphinx-doc.org>`_ into an html file
and displayed in a help panel close to the transformation widget.

The main application help files are also built at the start up time if ParSeq
file have been modified.

About dialog
~~~~~~~~~~~~

The about dialog displays the connectivity between the pipeline nodes in a
dynamically created svg graph. If a fit is defined in a node, it is also
displayed here.

Prepare pipeline metadata and images
------------------------------------

Create a project directory for the pipeline. Create `__init__.py` file that
defines metadata about the project. Note that pipeline applications and ParSeq
itself use the module `parseq.core.singletons` as a means to store global
variables; the pipeline's `__init__.py` module defines a few of them. Together
with the docstrings of the module, these metadata will appear in the About
dialog.

Create `doc/_images` directory and put an application icon there. The pipeline
transformations will have class docstrings that may also include images; those
images should be located here, in `doc/_images`.

Make data nodes
---------------

To define a node class means to name all plot arrays, define their roles,
labels and units. The data containers may also have other array attributes that
do not participate in plots; these are not to be declared.

Make data transformations
-------------------------

Start making a transformation class with defining a dictionary `defaultParams`
of default parameter values. Decide on using multiprocessing/multithreading by
specifying `nThreads` or `nProcesses`. If any of these numbers is > 1 (the
default values are both 1), specify two lists of array names: `inArrays` and
`outArrays`. Define a static or a class method :meth:`.Transform.run_main`.
Note, it can have a few signatures. Within the method, get the actual
transformation parameters from the dictionary `data.transformParams` and get
data arrays as attributes of `data`, e.g. ``data.x``.

For expensive transformations, you should update the *progress* status.

For accessing arrays of other data objects, use a different signature of
:meth:`.Transform.run_main` that contains the *allData* argument. Note that in
this case multiprocessing is not possible.

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

Provide docstrings in reStructuredText markup. They will be built by Sphinx and
displayed near the corresponding widgets.

Make fitting worker classes
---------------------------

Similarly to a transformation class, a fitting class defines multiprocessing /
multithreading needs and a static or a class method :meth:`.Fit.run_main`. It
also defines in a few class dictionaries the data array to be fitted and the
fit parameters.

Make data pipeline
------------------

This is a small module that instantiates the above nodes, transformations, fits
and widgets and connects them together.

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

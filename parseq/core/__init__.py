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

An analysis pipeline is a sequence of *nodes* connected by data
*transformations*. Nodes serve as intermediate stages where results can be
visualized, evaluated, and the transformations interactively controlled.
See an example on the right.

Data nodes define array names that are exposed as attributes of data objects.
The values of these arrays are either read from input files or computed from
other arrays. The pipeline can operate both with and without a graphical user
interface. When used with GUI widgets, the arrays defined in each node are
visualized in the node's plot, which may be 1D, 2D, or 3D (represented as a
stack of 2D plots).

.. imagezoom:: _images/pipeline-data-tree.png
   :alt: &ensp;EXAFS spectra arranged in a tree. The item tooltips present data
       flow information, array sizes and error messages.

The data tree model (following Qt's `Model/View Programming
<https://doc.qt.io/qt-6/model-view-programming.html>`_ concept) is implemented
as a single object shared across the entire pipeline. In contrast, data tree
widgets -- see an example on the left -- are present in *each* data node rather
than as a single instance. This design also allows them to serve as plot
legends.

The data tree can be populated from the file tree via a context menu or by
drag-and-drop actions. Newly loaded data inherit transformation parameters from
the currently active data item (or from the first one if multiple items are
active). If no data have been loaded yet, the parameters are read from an .ini
file. If no such file exists, default values are taken from the `defaultParams`
dictionary defined in each transformation class.

Users can rearrange the data by sorting, renaming, grouping, or removing items.
The selection state in the data model is shared across all transformation nodes.
For 1D data, line colors remain consistent across all nodes.

Plotting behavior depends on data dimensionality: For 1D data, multiple curves
can be displayed simultaneously. These can be selected either dynamically (via
mouse interaction) or statically (via checkboxes). The mode is controlled by
clicking the header of the visibility column, which toggles between single-eye
and multi-eye icons. For 2D and 3D data, only one dataset is displayed at a
time -- the first among the selected items.

Each transformation class defines a dictionary of parameters along with their
default values, and provides a static method for computing the corresponding
data arrays. Transformation parameters are stored with each data object and are
typically modified through GUI widgets. These modifications can be applied to
one or multiple active datasets simultaneously. Additionally, individual
parameters can be copied from one dataset to one or more subsequently selected
datasets.

.. imagezoom:: _images/pipeline-transform-apply.png
   :align: right
   :alt: &ensp;An example of the apply/reset popup menu on a control element.

Each transformation can optionally specify the number of threads or processes
used to execute the transformation in parallel across multiple data items. When
using Python's multiprocessing API, the main transformation method must be
defined as a *static* or *class* method rather than an instance method. In
addition, to enable inter-process data transfer, all input and output node
arrays must be explicitly listed in the ``inArrays`` and ``outArrays``
attributes of the transformation class.

In the pipeline GUI, interactive elements can be registered using dedicated
methods provided by the base class :class:`PropWidget`. This registration
enables (a) automatic synchronization of the GUI with the active data, along
with triggering transformations when GUI values are updated -- thus typically
eliminating the need for explicit
`signal slots <https://doc.qt.io/qt-6/signalsandslots.html>`_ connections.
It also enables (b) copying of transformation parameters to other datasets via
context menus available on each GUI element (see example on the right).

Docked node widgets
~~~~~~~~~~~~~~~~~~~

To enable flexible use of screen space, node widgets are designed to be
detachable from and dockable into the main ParSeq window. A widget can be
detached by dragging its title bar. To dock it again, either hover it over the
main window or use the dock button located at the right end of the title bar.

The state of each node widget (docked or floating), along with its floating
geometry, is saved in both the .ini configuration file and project files.

Undo and redo
~~~~~~~~~~~~~

.. imagezoom:: _images/pipeline-undo.png
   :align: left
   :alt: &ensp;The undo menu where individual actions can be reverted or
       deleted. The most typical way of using undo is to sequentially reverse
       actions from the top of the undo stack, either by the Undo button or the
       standard key combination Ctrl+Z.

Changes to transformation parameters can be undone and redone using the
undo/redo actions. Adding or removing data items can also be reverted.
ParSeq retains references to deleted data items so that they can be restored.
To free memory occupied by these items, the undo/redo history can be cleared
manually.

File tree views and file formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each transformation node has its own file tree view, with a data format widget
located at the bottom. By default, the file tree is visible only in the
pipeline head node(s). Its visibility can be toggled using the vertical button
of the leftmost splitter widget labeled "files & containers".

The file tree model combines Qt's QFileSystemModel with silx's Hdf5TreeModel,
allowing HDF5 files to appear as subdirectories within the same tree.

When an entry in the data tree is selected, the corresponding file or HDF5
entry is highlighted in the starting transformation node. During file browsing,
entries are highlighted in green if they can be loaded, i.e. if the fields in
the data format widget are properly defined and valid.

.. imagezoom:: _images/pipeline-file-tree.png
   :align: right
   :alt: &ensp;The file tree of a node. Visible is an expanded entry of an hdf5
       file. The sum of the two selected arrays will define I0 array.

ParSeq supports two types of input files: column-based text files and HDF5 files.

For column files, format definitions are specified as expressions involving
variables `Col0`, `Col1`, etc., for example `Col3 + Col4`. Simple expressions
such as `Col0` can be reduced to the corresponding column index, here `0`.
These expressions may also include NumPy functions, for example
`np.log(Col6/Col7)`.

The file header can optionally be defined by the number of header lines, a
leading comment character, or a keyword present in the last header line. The
entire header is stored as metadata for the corresponding data item.

In some cases, column files may contain a variable number or arrangement of
columns, depending on the instrument used. ParSeq can handle such cases
automatically if the pipeline provides a node method `auto_format()` which
parses the file header to identify column indices. An example implementation
can be found in the ParSeq-XAS pipeline (see `XAS_nodes.py`).

For HDF5 files, format definitions are given as relative dataset paths or as
expressions based on a data dictionary `d`, whose keys correspond to these
paths. For example:
`d["measurement/albaem-01_ch1"] + d["measurement/albaem-01_ch2"]`.
These expressions can be conveniently constructed using the context menu in the
file tree view (see image on the right). String or scalar HDF5 entries can
similarly be added to the list of metadata items via the same menu. Note that
datasets can be combined from different groups or even different HDF5 files
when forming a single data item.

Format definitions are preserved between sessions and automatically restored at
program startup. The data format widget updates according to the currently
selected data item. When multiple formats are used within a session, selecting
an appropriate data item ensures that the corresponding format is active before
loading similar data.

Format definitions can also be saved to an .ini file (.parseq/formats.ini) and
later restored via the context menu by right-clicking a data file.

Automatic data loading can be enabled using the
"auto load new data from current location" checkbox, which is particularly
useful during beamtime measurements.

Metadata
~~~~~~~~

The metadata widget aggregates metadata string variables (see the previous
section). The same widget can also be used to inspect text files and identify
column positions via the context menu in the file tree view. The widget is
hidden by default and is located below the node plot.

Plots
~~~~~

.. imagezoom:: _images/pipeline-line-props.png
   :align: right
   :alt: &ensp;Line properties accessed from the header of a node's data tree.

Node plots are used both for data visualization and for hosting analysis tools
such as regions of interest (ROIs) and data correction widgets. The 1D, 2D and
3D (2D stack) plots are based on the silx library with additional
customizations.

Note that if multiple data items share the same alias, silx will display only
one of them. Therefore, aliases should be unique. ParSeq attempts to ensure
uniqueness by appending a numeric suffix when multiple datasets originate from
files with the same name. Aliases can always be modified by the user.

In the 1D plotting window, clicking on a curve selects the corresponding data
item in the data tree. Additional (auxiliary) curves can be defined within user
transformations via an `extraPlot()` method. These curves should have their
legend property formatted as <data alias>.<sub-name>. When this convention is
followed, the curves become clickable, allowing selection of the associated
data item in the data tree. Selected items are rendered on top of others.

Default plot settings for 1D curves can be specified in the definitions of node
arrays. These settings can also be modified through any data tree view in the
GUI (see example on the right).

The silx plotting framework supports multiple rendering backends, currently
including 'matplotlib' and 'opengl'. In ParSeq, 'matplotlib' is the default due
to its generally better visual quality, while 'opengl' provides faster
performance, especially for 2D and 3D plots. Users can select the desired
backend via command-line options of the pipeline starter.

Fits
~~~~

Data nodes can optionally include curve-fitting routines. When one or more
fitting widgets are defined for a node, they appear in separate splitter panels
below the node's plot. By default, these panels are collapsed in the initial
view.

.. imagezoom:: _images/pipeline-fit-EXAFS.png
   :align: right
   :alt: &ensp;EXAFS fit widget as an example of ParSeq fit widgets. It was
       built on top of the ParSeq base fit and base fit widget classes.

Similarly to transformations, fitting solvers can run in parallel across
multiple data items. Fit parameters can be constrained or linked to other
parameters, including those from fits of different data items. An example fit
widget is shown on the right.

ParSeq provides a base fit class, :class:`parseq.fits.basefit.Fit` along with
its GUI counterpart :class:`parseq.gui.fits.gbasefit.FitWidget`. These serve as
parent classes for built-in Linear Combination Fit, Function Fit and EXAFS Fit.

Each fit execution is performed by a worker based on
`scipy.optimize.curve_fit
<https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html>`_.
Performance metrics are displayed at the bottom of each fit widget.

Cross-data combinations
~~~~~~~~~~~~~~~~~~~~~~~

Data items within each transformation node can be combined to produce secondary
datasets, such as averages, sums, and RMS deviations. For 1D data, additional
methods are available, including classical PCA, cumulative PCA, Target
Transformation and MCR-ALS.

If the abscissa values of the input datasets differ (in the case of 1D data),
interpolation is provided to align them before performing the combination.

Standard data corrections
~~~~~~~~~~~~~~~~~~~~~~~~~

ParSeq data pipelines perform data processing through specialized
*transformations*. In addition, ParSeq provides a set of standard data
*corrections* designed for refining experimental 1D data curves. These include
(a) range deletion, (b) vertical scaling within a selected range, (c)
spline-based replacement and (d) step correction.

Although ParSeq pipelines can operate without a GUI, data corrections are most
conveniently performed interactively using the mouse.

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

Each pipeline application includes several example project files. A ParSeq
project file (.pspj) defines the data tree along with all parameters for
transformations and fits. It follows the `ini file structure
<https://docs.python.org/3/library/configparser.html>`_. When saving a project,
ParSeq also stores relevant plot views, which can be previewed in the *Load
project* dialog, see on the left.

Before opening the *Save Project* dialog, select the data items to be exported.
In the dialog, choose the nodes to export from, the desired data formats, and
whether to generate a plotting script. This script visualizes the exported data
while preserving the plotting settings from the analysis pipeline. Its purpose
is twofold: to demonstrate how to access the saved data and to provide a
starting point for further customization of figures. The script includes
comments describing how to adjust axis ranges, labels, and curve legends.

In the saved project, the file path for each data item is stored in both
absolute and relative forms (relative to the project location). This allows the
project to be relocated together with its data files and still be loaded
correctly. However, when copying from certain environments (e.g. GPFS at
beamlines), the relative paths may require manual adjustment using a
search/replace operation in a text editor.

Error handling
~~~~~~~~~~~~~~

If an error occurs during a transformation, it is caught by ParSeq. The
corresponding data item is then marked as invalid and highlighted with a red
background in the data tree. Details of the error are available in the tooltip
of the affected item, including the transformation name, the data item, and the
involved Python module. The error message can also be copied to the clipboard.

In addition, errors are recorded in the pipeline log file. This file is located
in the user's home directory under the .parseq subfolder. Note that the log
file is limited to a single program session and is reset when the application
is restarted. The logging level depends on the verbosity settings specified via
command-line options.

Command-line interface and start options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The available command-line options of the starter script can be displayed
using the :command:`--help` option. Most of these options are primarily
intended for development purposes.

Performance profiling
~~~~~~~~~~~~~~~~~~~~~

When the starter script is run with an elevated verbosity level (e.g. using
the :command:`--verbosity 100` option), the terminal output includes timing
information for each relevant invocation of transformation and plotting methods,
as shown below. This feature is primarily intended as a tool for developing and
optimizing data pipelines.

.. imagezoom:: _images/pipeline-timing.png
   :align: none
   :alt: &ensp;An example of the terminal output with timing figures, enabled
       by the CLI option `--verbosity` (*or* `-v`).

Help system
~~~~~~~~~~~

Transformation class docstrings are processed by ParSeq at application startup
using `Sphinx <https://www.sphinx-doc.org>`_, generating HTML documentation
that is displayed in a help panel adjacent to the transformation widget.

The main application help files are also rebuilt at startup if the ParSeq
source files have been modified.

If the generated HTML output appears incorrect, troubleshooting should begin by
running the application with an elevated verbosity level
(e.g. `python XAS_start.py -v 10`) to inspect the Sphinx build output. The
generated HTML file can then be opened in an external browser, where developer
tools can be used to examine issues such as missing images, incorrect paths or
CSS problems.

The documentation can also be manually rebuilt using the "Rebuild documentation"
command available in the application's top menu.

About dialog
~~~~~~~~~~~~

The *About* dialog displays the connectivity between pipeline nodes as a
dynamically generated SVG graph. If a fitting routine is defined within a node,
it is also included in this visualization.

Prepare pipeline metadata and images
------------------------------------

Create a project directory for the pipeline and add an `__init__.py` file that
defines the project metadata. Both pipeline applications and ParSeq itself use
the module `parseq.core.singletons` to store global variables; the pipeline's
`__init__.py` module is responsible for defining several of these. Together
with the module's docstrings, this metadata is displayed in the About dialog.

Create a `doc/_images` directory and place the application icon there.
Transformation class docstrings may also include images; these should likewise
be stored in the `doc/_images` directory.

Make data nodes
---------------

Defining a node class involves specifying all arrays to be plotted, including
their roles, labels, and units. Data containers may also include additional
arrays that are not used for plotting; such arrays do not need to be declared.

Make data transformations
-------------------------

Start implementing a transformation class by defining a dictionary
`defaultParams` containing default parameter values. Specify whether to use
multiprocessing or multithreading by setting `nProcesses` or `nThreads`. If
either value exceeds 1 (both default to 1), you must also define two lists of
array names: `inArrays` and `outArrays`.

Implement the main transformation logic in a *static* or *class* method,
:meth:`.Transform.run_main`. Note that this method supports multiple signatures.
Within it, access the current transformation parameters from
`data.transformParams`, and retrieve data arrays as attributes of data
(e.g. `data.x`).

For computationally intensive transformations, it is recommended to update the
*progress* status.

To access arrays from other data objects, use an alternative signature of
:meth:`.Transform.run_main` that includes the *allData* argument. Note that
multiprocessing is not supported in this case.

Make GUI widgets
----------------

Widgets that control transformation parameters are derived from
:class:`.PropWidget`. The key methods of this class are
:meth:`.PropWidget.registerPropWidget` and :meth:`.PropWidget.registerPropGroup`.
These methods leverage Qt's signal–slot mechanism to synchronize GUI elements
with transformation parameters, eliminating the need for users to explicitly
implement response slots.

In addition, they enable copying of transformation parameters to other data
items via context menus, update the GUI when different data objects are selected
in the data tree, trigger the associated transformation, and integrate with the
undo/redo mechanism.

Since each transformation already defines a set of default parameter values,
GUI widgets can be incrementally developed without disrupting the functionality
of the data pipeline.

All widgets should include docstrings in reStructuredText format. These are
processed by Sphinx and displayed alongside the corresponding widgets in the GUI.

Make fitting worker classes
---------------------------

Similarly to a transformation class, a fitting class specifies multiprocessing
or multithreading options and implements a static or class method,
:meth:`.Fit.run_main`. It also defines, through several class-level
dictionaries, the data array to be fitted and the associated fit parameters.

Make data pipeline
------------------

This module instantiates the defined nodes, transformations, fitting classes
and widgets, and connects them into a complete analysis pipeline.

Create test data tree
---------------------

Place a few data files in a local directory (e.g., `data`) and create a module
that defines a function to load these files into the :ref:`data tree <data>`.
This function should also set appropriate transformation parameters and trigger
the first transformation; subsequent transformations will be executed
automatically.

Create pipeline starter
-----------------------

The starter script should support command-line arguments, enabling options for
loading test data and running the pipeline both with and without a GUI.

Creating development versions of analysis application
-----------------------------------------------------

Copy the entire application folder to the same directory under a new name
(for example, by appending a version suffix). In the starter script, update the
import statements to refer to the newly created folder name. No further changes
are required.

"""

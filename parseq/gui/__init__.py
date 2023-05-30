# -*- coding: utf-8 -*-
u"""
Notes on usage of GUI
=====================

Load project
------------

To start testing a GUI, load a test project, typically located in `saved`
directory. The "Load project" dialog has a preview panel that displays all node
plots in the project, just browse over them. The initial visible plot displays
the transformation node that was active when the project was saved.

Docked node widgets
-------------------

With the idea of flexible usage of screen area, the node widgets were made
detachable and dockable into the main ParSeq window. To do this, drag a node
widget by its caption bar. To dock it back, hover it over the main window or
use the dock button at the right end of the caption bar.

The state of each node widget (docked or floating) and its floating geometry is
saved in ini file and project files.

File tree and data formats, metadata
------------------------------------

The file tree is by default visible only in the pipeline head node(s). If
needed, make it visible/hidden by the vertical button of the leftmost splitter
widget "files & containers".

When you click on an entry in the data tree, the corresponding file or hdf5
entry will get highlighted in the starting transformation node widget. When you
browse the file tree, the highlight color is green if this entry can be loaded,
i.e. the data format fields in the data format widget are defined. To define
the fields (array names), one can highlight one or several hdf5 datasets and
use popup menu commands. Note that you can use hdf5 data sets from various hdf5
data groups or even hdf5 data files, not necessarily from one data group when
you load one data item.

For column files, one should define the file header and expressions of
variables `Col0`, `Col1` etc. for data fields (arrays). If an array definition
is just a column, one can reduce it to the ordinal number of that column, so
type `0` instead of `Col0`.

Metadata can be composed of string hdf5 fields or for column files they are
copied from the header. Metadata are displayed in a panel below the plot in
each node.

The format fields in the "data format" dialog can be saved into an ini file
(.parseq/formats.ini) and later restored from it using the popup menu when
right-clicked on a data file.

The tabs of "data format" dialog have some help text in their tooltips.

Data tree
---------

The data tree can be populated from the file tree by using the popup menu or by
a drag-and-drop action.

The newly loaded data get their set of transformation parameters from the first
previously selected data item. If no items have been previously loaded, the
parameters are read from the ini file. If the ini file does not exist yet, the
parameters get their values from `defaultParams` defined in each transformation
class.

Use the popup menu or corresponding keyboard shortcuts to rearrange the data
tree.

The Qt tooltip on each data entry provides data path, shape and size. If an
error occurs during a transformation, the tooltip also contains the last
exception traceback.

In 1D transformation nodes, one can change the data visibility mode by clicking
on the "eye" header section. Try these modes while selecting different data
entries or groups.

Line properties of the selected data items can be set from the popup menu or by
clicking on the data column header. New data get their line properties from the
previously active data. The first data get their plot settings from the
optional `plotParams` of node’s arrays.

Combine dialog
--------------

A limited number of combination functions acting on several selected data items
can be performed via the "combine" dialog that can be found under the data tree
widget.

Plots
-----

All types of plots implemented in ParSeq are taken from `silx library
<https://www.silx.org/>`_.
Find more about their functionality `here
<http://www.silx.org/doc/silx/latest/modules/gui/plot/index.html?highlight=plot#module-silx.gui.plot>`_.

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
the data tree. Selected data items are plotted on top of unselected items.

Fit widgets
-----------

If one or more fit widgets were specified for a given node, they appear in
separate QSplitter under the node's plot. In the initial view, the splitters
are collapsed.

Help panel
----------

The help panel under transformation widgets is hidden by default and can be
made visible by clicking on the small button "help" at the very bottom of the
main window. Alternatively, it can be opened in the system browser.

About dialog
------------

The about dialog displays the connectivity between the pipeline nodes in a
dynamically created svg graph. If a fit is defined in a node, it is also
displayed here.

Undo and redo lists
-------------------

When a transformation parameter has been changed or a data item has been
deleted, this action is inserted into the undo list. Clicking on the big undo
button will revert the last action and put it into the redo list (not for the
undelete operation). Any undo action can also be executed separately, not
necessarily in the reverse order, by using the drop down-menu. Note, the undo
entry for a delete operation will keep the reference to the deleted item, so to
clean up the memory, this entry should be individually removed from the undo
list.

Save project, data and plot scripts
-----------------------------------

The present data tree and all transformation parameters of all data items can
be saved into a project file that has an ini text file structure.
Simultaneously, data arrays defined in each node can optionally be exported as
a few chosen data types. Note that data arrays will be exported only for the
currently selected data items, not for all data. Two types of data plotting
scripts can also be saved. These scripts will plot the exported data and are
provided with the idea to help the user adjust their publication quality
graphs.

In the saved project, file path to each data item is saved in two versions: as
an absolute path and as a relative path in respect to the project location.
When the project is copied together with the files to a new location, the
project should be directly loadable. When copied from a GPFS location at a
beamline, this may not work, and the relative paths have to be manually edited
by a Search/Replace operation in a text file editor.

"""

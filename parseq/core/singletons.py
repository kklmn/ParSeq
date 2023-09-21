# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "29 Sep 2022"
# !!! SEE CODERULES.TXT !!!

from collections import deque, OrderedDict
import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

DEBUG_LEVEL = 0

MAX_LEN_UNDO = 25
MAX_LEN_REDO = 25
undo = deque(maxlen=MAX_LEN_UNDO)
redo = deque(maxlen=MAX_LEN_REDO)
undoGrouping = True

# defined by the app
pipelineName = "must be defined by the app"
appPath = "must be defined by the app"
appIconPath = None
appIconScale = 1.
appSynopsis = None
appDescription = None
appAuthor = None
appLicense = None
appVersion = None
# end defined by the app

nodes = OrderedDict()
transforms = OrderedDict()
fits = OrderedDict()
# transformWidgets = OrderedDict()
mainWindow = None
currentNode = None

withGUI = 'not set yet'
# updated later by MainWindowParSeq as qt.qApp.desktop().logicalDpiX() / 120.:
screenFactor = 1

dataRootItem = None
extraDataFormat = {}
model = None  # dataTreeModelView.DataTreeModel()
modelDataColumns = []  # (node, arrayName)
modelLeadingColumns = ['data name', '']  # the last one is for view state (eye)

selectionModel = None
selectedItems, selectedTopItems = [], []  # common for all data trees
recentlyLoadedItems = []
allLoadedItems = []

# tasker will be created in MainWindow ParSeq init
tasker = None

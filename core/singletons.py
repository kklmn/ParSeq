# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from collections import deque, OrderedDict

DEBUG_LEVEL = 1

MAX_LEN_UNDO = 25
MAX_LEN_REDO = 25
undo = deque(maxlen=MAX_LEN_UNDO)
redo = deque(maxlen=MAX_LEN_REDO)
undoGrouping = True

pipelineName = "must be defined by the app"
appPath = "must be defined by the app"
appIconPath = None
appIconScale = 1.
appSynopsis = None
appDescription = None
appAuthor = None
appLicense = None
appVersion = None

nodes = OrderedDict()
transforms = OrderedDict()
# transformWidgets = OrderedDict()
mainWindow = None
currentNode = None

withGUI = 'not set yet'

dataRootItem = None
extraDataFormat = {}
model = None  # dataTreeModelView.DataTreeModel()
modelDataColumns = []  # (node, arrayName)
modelLeadingColumns = ['data name', '']  # the last one is for view state (eye)
selectionModel = None
selectedItems, selectedTopItems = [], []  # common for all data trees
recentlyLoadedItems = []
allLoadedItems = []

# transformer will be created in MainWindow ParSeq init
transformer = None

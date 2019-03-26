# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from collections import deque, OrderedDict

MAX_LEN_UNDO = 100
MAX_LEN_REDO = 100
undo = deque(maxlen=MAX_LEN_UNDO)
redo = deque(maxlen=MAX_LEN_REDO)

pipelineName = "must be defined by the app"
appPath = "must be defined by the app"
appIconPath = None
appIconScale = 1.
appSynopsis = None
appDescription = None
appAuthor = None
appLicense = None

nodes = OrderedDict()
transforms = OrderedDict()
transformWidgets = OrderedDict()
mainWindow = None
currentNodeToDrop = None

withGUI = 'not set yet'

dataRootItem = None
smodel = None  # dataTreeModelView.DataTreeModel()
modelDataColumns = []  # (node, yNames) of all nodes as headers in data model
modelLeadingColumns = ['data name', '']
selectionModel = None
selectedItems, selectedTopItems = [], []  # common for all data trees
recentlyLoadedItems = []
allLoadedItems = []

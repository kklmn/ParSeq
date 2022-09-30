# coding: utf-8
import sys
import os
from PyQt5 import QtCore, QtWidgets

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    path = os.path.realpath(r"c:\_MaxIV\Balder data\20220706-XES-HERFD-NiCoFe")
    model = QtWidgets.QFileSystemModel()
    rootIndex = model.setRootPath(path)
    model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.AllEntries |
                    QtCore.QDir.NoDotAndDotDot)

    treeView = QtWidgets.QTreeView()
    treeView.setModel(model)
    treeView.setRootIndex(model.index(path))
    treeView.setColumnWidth(0, 250)

    proxyModel = QtCore.QSortFilterProxyModel()
    proxyModel.setSourceModel(model)
    # !!!!!!
    # For hierarchical models, the filter is applied recursively to all
    # children. If a parent item doesn't match the filter, none of its children
    # will be shown.
    # !!!!!!
    # proxyModel.setFilterRegularExpression(r"^((?!eiger).)*$")
    proxyModel.setFilterRegularExpression(r"^((?!eiger)(?!CoSn).)*$")
    # proxyModel.setFilterRegularExpression(r"^(.)*$")

    treeViewProxy = QtWidgets.QTreeView()
    treeViewProxy.setModel(proxyModel)
    treeViewProxy.setRootIndex(proxyModel.mapFromSource(model.index(path)))
    treeViewProxy.setColumnWidth(0, 250)

    w = QtWidgets.QWidget()
    hlay = QtWidgets.QHBoxLayout(w)
    hlay.addWidget(treeView)
    hlay.addWidget(treeViewProxy)
    w.setMinimumSize(1400, 500)
    w.show()

    sys.exit(app.exec_())

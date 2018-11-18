# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
import parseq.core.singletons as csi
import parseq.core.spectra as csp
from parseq.gui.treeModelView import TreeModel, TreeView

MyTreeView = TreeView


def test_TreeItem(withGUI):
    from parseq.core.spectra import TreeItem
    csi.dataRootItem = TreeItem('root')
    rootItem = csi.dataRootItem

    testdata = [
            ['z', 'AA?group AA', ['a1', 'b1', ['BB?BBBB', ['c', 'a2']], 'b2']],
            ['d1', 'd2', 'd3', 'e1'],
            ['e2']*3,
            ['CC', ['f', 'g', 'h']],
            ['i', 'j', 'k'],
            'xx', 'yy', 'zz']
#    testdata = ['AA?group AA', ['a1', 'b1', ['BB?BBBB', ['c', 'a2']], 'b2']]
#    testdata = []

    if withGUI:
        app = qt.QApplication(sys.argv)
        model = TreeModel()
        csi.model = model
        view = MyTreeView()

        if "qt5" in qt.BINDING.lower():
            from modeltest import ModelTest
            ModelTest(model, view)

        view.setWindowTitle("Simple Tree Model")

        items = model.importData(testdata)
#        items = model.rootItem.insert_data(testdata)

        view.show()
        app.exec_()
    else:
        items = rootItem.insert_data(testdata)
        print([item.alias for item in items])

        # another way of getting all data is by rootItem.get_items():
        print([item.alias for item in rootItem.get_items()])

        # yet another way of getting recently loaded data:
        print([item.alias for item in csi.recentlyLoadedItems])


def test_Spectrum1(withGUI):  # without convenience functions
    import parseq.apps.dummy as myapp

    myapp.make_pipeline(withGUI)
    rootItem = csi.dataRootItem

    fNames = [['../data/Cu_lnt1.fio', (3, 5, 6)],  # fname and columns to use
              ['../data/Cu_lnt2.fio', (3, 5, 6)],
              ['../data/Cu_rt1.fio', (3, 5, 6)],
              ['../data/Cu_rt2.fio', (3, 5, 6)],
              ['../data/Cu2O_lnt1.fio', (0, 5, 6)],
              ['../data/Cu2O_lnt2.fio', (0, 5, 6)],
              ['../data/CuO_lnt.fio', (0, 5, 6)]]

    if withGUI:
        app = qt.QApplication(sys.argv)
        model = csi.model
        node = list(csi.nodes.values())[0]
        view = MyTreeView(node)
        view.setWindowTitle("Spectra Tree Model")

        for i in range(3):
            group0, = model.importData('metal')
# or        group0, = model.rootItem.insert_data('metal')
            dataFormat = dict(usecols=fNames[0][1], lastSkipRowContains='Col ')
            data = [fn[0] for fn in fNames[:4]]
            items0 = model.importData(data, group0, dataFormat=dataFormat)
# or        items0 = group0.insert_data(data, dataFormat=dataFormat)
            group1, = model.importData('oxides')
# or        group1, = model.rootItem.insert_data('oxides')
            dataFormat = dict(usecols=fNames[4][1], lastSkipRowContains='Col ')
            data = [fn[0] for fn in fNames[4:7]]
            items1 = model.importData(data, group1, dataFormat=dataFormat)
# or        items1 = group1.insert_data(data, dataFormat=dataFormat)
#            view.dataChanged()  # if via group.insert_data()

        if "qt5" in qt.BINDING.lower():
            from modeltest import ModelTest
            ModelTest(model, view)

        view.show()
        app.exec_()
    else:
        for i in range(3):
            group0, = rootItem.insert_data('metal')
            dataFormat = dict(usecols=fNames[0][1], lastSkipRowContains='Col ')
            data = [fn[0] for fn in fNames[:4]]
            items0 = group0.insert_data(data, dataFormat=dataFormat)
            group1, = rootItem.insert_data('oxides')
            dataFormat = dict(usecols=fNames[4][1], lastSkipRowContains='Col ')
            data = [fn[0] for fn in fNames[4:7]]
            items1 = group1.insert_data(data, dataFormat=dataFormat)

        print([item.alias for item in rootItem.get_items()])
        print([item.alias for item in csi.recentlyLoadedItems])


def test_Spectrum2(withGUI):  # with convenience functions
    import parseq.apps.dummy as myapp

    myapp.make_pipeline(withGUI)
    myapp.load_test_data()

    if withGUI:
        app = qt.QApplication(sys.argv)
        node = list(csi.nodes.values())[0]
        view1 = MyTreeView(node)

        if "qt5" in qt.BINDING.lower():
            from modeltest import ModelTest
            ModelTest(csi.model, view1)

        view1.setWindowTitle("Spectra Tree Model")

        view1.show()
        app.exec_()


if __name__ == '__main__':
#    test_TreeItem(withGUI=True)
#    test_TreeItem(withGUI=False)

#    test_Spectrum1(withGUI=True)
#    test_Spectrum1(withGUI=False)

    test_Spectrum2(withGUI=True)
#    test_Spectrum2(withGUI=False)

# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Aug 2022"
# !!! SEE CODERULES.TXT !!!

import os, sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
# import parseq.core.spectra as csp


def test_TreeItem(withGUI):
    from parseq.core.spectra import TreeItem

    if withGUI:
        from parseq.tests import testapp
        testapp.make_pipeline(withGUI)
        testapp.load_test_data()

        from silx.gui import qt
        from parseq.gui.dataTreeModelView import DataTreeView
        MyTreeView = DataTreeView

        app = qt.QApplication(sys.argv)
        view = MyTreeView()

        if "qt5" in qt.BINDING.lower():
            from modeltest import ModelTest
            ModelTest(csi.model, view)

        view.setWindowTitle("Simple Tree Model")

        view.show()
        app.exec_()
    else:
        testdata = [
                ['z', 'AA?group AA', ['a1', 'b1',
                                      ['BB?BBBB', ['c', 'a2']], 'b2']],
                ['d1', 'd2', 'd3', 'e1'],
                ['e2']*3,
                ['CC', ['f', 'g', 'h']],
                ['i', 'j', 'k'],
                'xx', 'yy', 'zz']
        # testdata = ['AA?group AA', ['a1', 'b1',
        #                             ['BB?BBBB', ['c', 'a2']], 'b2']]
        # testdata = []

        csi.dataRootItem = TreeItem('root')
        rootItem = csi.dataRootItem
        items = rootItem.insert_data(testdata)
        print(repr(rootItem.childItems))

        print([item.alias for item in items])

        # another way of getting all data is by rootItem.get_items():
        print([item.alias for item in rootItem.get_items()])

        # yet another way of getting recently loaded data:
        print([item.alias for item in csi.recentlyLoadedItems])


def test_Spectrum(withGUI):  # with convenience functions
    from parseq.tests import testapp

    testapp.make_pipeline(withGUI)
    testapp.load_test_data()

    if withGUI:
        from silx.gui import qt
        from parseq.gui.dataTreeModelView import DataTreeView
        MyTreeView = DataTreeView

        app = qt.QApplication(sys.argv)
        node = list(csi.nodes.values())[-1]
        view1 = MyTreeView(node)

        if "qt5" in qt.BINDING.lower():
            from modeltest import ModelTest
            ModelTest(csi.model, view1)

        view1.setWindowTitle("Spectra Tree Model")
        # select the 1st item (it is a group)
        view1.setCurrentIndex(csi.model.index(0))

        view1.show()
        app.exec_()


if __name__ == '__main__':
    # test_TreeItem(withGUI=False)
    # test_TreeItem(withGUI=True)
    test_Spectrum(withGUI=True)

# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "19 Jul 2022"
# !!! SEE CODERULES.TXT !!!

import os
import numpy as np
import pickle
import json
import autopep8

import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"
import h5py

from ..core import config
from ..core import singletons as csi
from ..core import spectra as csp
from ..gui import gcommons as gco

__fdir__ = os.path.abspath(os.path.dirname(__file__))
chars2removeMap = {ord(c): '-' for c in '/*? '}


def load_project(fname, qMessageBox=None, restore_perspective=None):
    configProject = config.ConfigParser()
    configProject.optionxform = str  # makes it case sensitive
    try:
        configProject.read(fname)
    except Exception:
        if qMessageBox is None:
            print("Invalid project file {0}".format(fname))
        else:
            qMessageBox.critical(None, "Cannot load project",
                                 "Invalid project file {0}".format(fname))
        return
    if restore_perspective:
        restore_perspective(configProject)
    dataTree = config.get(configProject, 'Root', 'tree', [])
    if not dataTree:
        print("No valid data tree specified in this project file")
        return
    root = csi.dataRootItem
    colorPolicyName = config.get(configProject, 'Root', 'colorPolicy',
                                 gco.COLOR_POLICY_NAMES[1])
    root.colorPolicy = gco.COLOR_POLICY_NAMES.index(colorPolicyName)
    if root.colorPolicy == gco.COLOR_POLICY_GRADIENT:
        root.color1 = config.get(configProject, 'Root', 'color1', 'r')
        root.color2 = config.get(configProject, 'Root', 'color2', 'b')
    elif root.colorPolicy == gco.COLOR_POLICY_INDIVIDUAL:
        root.color = config.get(configProject, 'Root', 'color', 'm')
    root.colorAutoUpdate = config.get(
        configProject, 'Root', 'colorAutoUpdate',
        csp.DEFAULT_COLOR_AUTO_UPDATE)

    os.chdir(os.path.dirname(fname))
    if csi.model is not None:
        csi.model.importData(dataTree, configData=configProject)
    else:
        items = root.insert_data(dataTree, configData=configProject)
        run_transforms(items, root)


def run_transforms(items, parentItem):
    topItems = [it for it in items if it in parentItem.childItems]
    bottomItems = [it for it in items if it not in parentItem.childItems
                   and (not isinstance(it.madeOf, dict))]
    # branchedItems = [
    #     it for it in items if it not in parentItem.childItems
    #     and isinstance(it.madeOf, dict)]

    # first bottomItems, then topItems...:
    if len(csi.transforms.values()) > 0:
        tr = list(csi.transforms.values())[0]
        if csi.transformer is not None:  # with a threaded transform
            csi.transformer.prepare(
                tr, dataItems=bottomItems+topItems, starter=tr.widget)
            csi.transformer.thread().start()
        else:  # in the same thread
            tr.run(dataItems=bottomItems+topItems)
            if hasattr(tr, 'widget'):  # when with GUI
                tr.widget.replotAllDownstream(tr.name)


def save_project(fname, save_perspective=None):
    configProject = config.ConfigParser(allow_no_value=True)
    configProject.optionxform = str  # makes it case sensitive

    root = csi.dataRootItem
    config.put(configProject, 'Root', 'tree', repr(root))
    config.put(configProject, 'Root', 'colorPolicy',
               gco.COLOR_POLICY_NAMES[root.colorPolicy])
    if root.colorPolicy == gco.COLOR_POLICY_GRADIENT:
        config.put(configProject, 'Root', 'color1', str(root.color1))
        config.put(configProject, 'Root', 'color2', str(root.color2))
    elif root.colorPolicy == gco.COLOR_POLICY_INDIVIDUAL:
        config.put(configProject, 'Root', 'color', str(root.color))
    config.put(configProject, 'Root', 'colorAutoUpdate',
               str(root.colorAutoUpdate))

    dirname = os.path.dirname(fname)
    for item in csi.dataRootItem.get_items(alsoGroupHeads=True):
        item.save_to_project(configProject, dirname)
    if save_perspective:
        save_perspective(configProject)
    with open(fname, 'w+') as cf:
        configProject.write(cf)


def save_data(fname, saveNodes, saveTypes, qMessageBox=None):
    if fname.endswith('.pspj'):
        fname = fname.replace('.pspj', '')

    plots = []
    if 'txt' in saveTypes:
        for iNode, ((nodeName, node), saveNode) in enumerate(
                zip(csi.nodes.items(), saveNodes)):
            if not saveNode:
                continue
            if node.plotDimension == 1:
                header = [node.plotXArray] + [y for y in node.plotYArrays]
            else:
                continue

            curves = {}
            for it in csi.selectedItems:
                dataToSave = [getattr(it, arr) for arr in header]
                nname = nodeName.translate(chars2removeMap)
                dname = it.alias.translate(chars2removeMap)
                sname = u'{0}-{1}-{2}'.format(iNode+1, nname, dname)
                # np.savetxt(sname+'.txt.gz', np.column_stack(dataToSave),
                np.savetxt(sname+'.txt', np.column_stack(dataToSave),
                           fmt='%.12g', header=' '.join(header))
                curves[sname] = [it.alias, it.color, header,
                                 it.plotProps[node.name]]

                for iG, aG in enumerate(node.auxArrays):
                    dataAux, headerAux = [], []
                    for yN in aG:
                        try:
                            dataAux.append(getattr(it, yN))
                        except AttributeError:
                            break
                        headerAux.append(yN)
                    if len(dataAux) == 0:
                        continue
                    sname = u'{0}-{1}-{2}-aux{3}'.format(
                            iNode+1, nname, dname, iG)
                    # np.savetxt(sname+'.txt.gz', np.column_stack(dataAux),
                    np.savetxt(sname+'.txt', np.column_stack(dataAux),
                               fmt='%.12g', header=' '.join(headerAux))
                    curves[sname] = [it.alias, it.color, headerAux]
            plots.append(['txt', node.name, node.plotDimension,
                          node.widget.getAxisLabels(), curves])

    if 'json' in saveTypes or 'pickle' in saveTypes:
        dataToSave = {}
        snames = []
        for it in csi.selectedItems:
            dname = it.alias.translate(chars2removeMap)
            snames.append(dname)
            dataToSave[it] = {}
        for node, saveNode in zip(csi.nodes.values(), saveNodes):
            if not saveNode:
                continue
            if node.plotDimension == 1:
                header = [node.plotXArray] + [y for y in node.plotYArrays]
            elif node.plotDimension == 2:
                header = node.plot2DArray
            elif node.plotDimension == 3:
                header = node.plot3DArray

            curves = {}
            for it, sname in zip(csi.selectedItems, snames):
                for aN in node.arrays:
                    dataToSave[it][aN] = getattr(it, aN).tolist()
                for aN in [j for i in node.auxArrays for j in i]:
                    try:
                        dataToSave[it][aN] = getattr(it, aN).tolist()
                    except AttributeError:
                        continue
                curves[sname] = [it.alias, it.color, header,
                                 it.plotProps[node.name]]
                if node.auxArrays:
                    headerAux = []
                    for aG in node.auxArrays:
                        for yN in aG:
                            if not hasattr(it, yN):
                                break
                        else:
                            headerAux.append(aG)
                    if headerAux:
                        curves[sname].append(headerAux)
            if 'json' in saveTypes and node.plotDimension == 1:
                plots.append(
                    ['json', node.name, node.plotDimension,
                     node.widget.getAxisLabels(), curves])
            if 'pickle' in saveTypes:
                plots.append(
                    ['pickle', node.name, node.plotDimension,
                     node.widget.getAxisLabels(), curves])

        for it, sname in zip(csi.selectedItems, snames):
            if 'json' in saveTypes and node.plotDimension == 1:
                with open(sname+'.json', 'w') as f:
                    json.dump(dataToSave[it], f)
            if 'pickle' in saveTypes:
                with open(sname+'.pickle', 'wb') as f:
                    pickle.dump(dataToSave[it], f)

    h5plots = []
    if 'h5' in saveTypes:
        dataToSave = {}
        snames = []
        for it in csi.selectedItems:
            dname = it.alias.translate(chars2removeMap)
            snames.append('data/' + dname)
            dataToSave[it] = {}
        for node, saveNode in zip(csi.nodes.values(), saveNodes):
            if not saveNode:
                continue
            if node.plotDimension == 1:
                header = [node.plotXArray] + [y for y in node.plotYArrays]
            elif node.plotDimension == 2:
                header = node.plot2DArray
            elif node.plotDimension == 3:
                header = node.plot3DArray

            curves = {}
            for it, sname in zip(csi.selectedItems, snames):
                for aN in node.arrays:
                    dataToSave[it][aN] = getattr(it, aN)
                for aN in [j for i in node.auxArrays for j in i]:
                    try:
                        dataToSave[it][aN] = getattr(it, aN)
                    except AttributeError:
                        continue
                curves[sname] = [it.alias, it.color, header,
                                 it.plotProps[node.name]]
                if node.auxArrays:
                    headerAux = []
                    for aG in node.auxArrays:
                        for yN in aG:
                            if not hasattr(it, yN):
                                break
                        else:
                            headerAux.append(aG)
                    if headerAux:
                        curves[sname].append(headerAux)
            h5plots.append([node.name, node.plotDimension,
                            node.widget.getAxisLabels(), curves])

        try:
            with h5py.File(fname+'.h5', 'w') as f:
                dataGrp = f.create_group('data')
                plotsGrp = f.create_group('plots')
                for it in csi.selectedItems:
                    dname = it.alias.translate(chars2removeMap)
                    if dname in f:
                        continue
                    grp = dataGrp.create_group(dname)
                    for aN in dataToSave[it]:
                        if aN in grp:
                            continue
                        com = None if np.isscalar(dataToSave[it][aN]) else\
                            'gzip'
                        grp.create_dataset(aN, data=dataToSave[it][aN],
                                           compression=com)
                    grp.create_dataset('transformParams',
                                       data=str(it.transformParams))
                for plot in h5plots:
                    grp = plotsGrp.create_group(plot[0])
                    grp.create_dataset('ndim', data=plot[1])
                    grp.create_dataset('axes', data=str(plot[2]))
                    grp.create_dataset('plots', data=str(plot[3]))
        except Exception as e:
            if qMessageBox is None:
                print("Cannot write file {0}".format(fname))
            else:
                qMessageBox.critical(
                    None, "Cannot write file {0}".format(fname), str(e))

    return plots, h5plots


def _script(lines, sname):
    for i, line in enumerate(lines):
        if 'def ' + sname in line:
            istart = i
        if 'end ' + sname in line:
            iend = i
            break
    else:
        return []
    return lines[istart-2: iend+1]


def save_script(fname, plots, h5plots, lib='mpl'):
    if len(plots) == len(h5plots) == 0:
        print("no plots selected")
        return
    if fname.endswith('.pspj'):
        fname = fname.replace('.pspj', '')
    basefname = os.path.basename(fname)

    pyExportMod = os.path.join(__fdir__, 'plotExport.py')
    with open(pyExportMod, 'r') as f:
        lines = [line.rstrip('\n') for line in f]

    output = lines[:2]
    if lib == 'mpl':
        output.extend(lines[2:4])

    output.extend(_script(lines, "readFile"))
    dims = set([plot[2] for plot in plots] + [plot[1] for plot in h5plots])
    for dim in [1, 2, 3]:
        if dim in dims:
            output.extend(_script(lines, "read{0}D".format(dim)))
            output.extend(_script(lines, "plot{0}D{1}".format(dim, lib)))

    if len(h5plots) > 0:
        output.extend(_script(lines, "getPlotsFromHDF5"))
    output.extend(_script(lines, "plotSavedData"))
    output.extend(["", "", "if __name__ == '__main__':"])

    if len(plots) == 0:
        output.extend(["    h5name = '{0}.h5'".format(basefname),
                       "    plots = getPlotsFromHDF5(h5name)"])
    elif len(h5plots) == 0:
        output.append("    plots = {0}".format(
            autopep8.fix_code(repr(plots), options={'aggressive': 2})))
    else:
        output.extend([
            "    # you can get plot definitions from the h5 file:",
            "    # h5name = '{0}.h5'".format(basefname),
            "    # plots = getPlotsFromHDF5(h5name)", "",
            "    # ...or from the `plots` list:",
            "    plots = {0}".format(
                autopep8.fix_code(repr(plots), options={'aggressive': 2}))
            ])
    if lib == 'silx':
        output.extend(["    from silx.gui import qt",
                       "    app = qt.QApplication([])"])
    output.extend(["    plotSavedData(plots, '{0}')".format(lib), ""])
    if lib == 'silx':
        output.extend(["    app.exec_()"])

    fnameOut = '{0}_{1}.py'.format(fname, lib)
    with open(fnameOut, 'w') as f:
        f.write('\n'.join(output))

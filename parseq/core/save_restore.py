# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "6 Dec 2024"
# !!! SEE CODERULES.TXT !!!

import os
import numpy as np
import pickle
import json
import datetime
import autopep8

os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"  # to work with external links
# import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"
import h5py

from ..core import config
from ..core import singletons as csi
from ..core import spectra as csp
from ..core import transforms as ctr
from ..core.logger import syslogger
from ..gui import gcommons as gco
from ..version import __versioninfo__, __version__, __date__

__fdir__ = os.path.abspath(os.path.dirname(__file__))
chars2removeMap = {ord(c): '-' for c in '/*? '}
encoding = config.encoding


def load_project(fname, qMessageBox=None, restore_perspective=None):
    configProject = config.ConfigParser()
    configProject.optionxform = str  # makes it case sensitive
    try:
        with open(fname, encoding=encoding) as f:
            configProject.read_file(f)
    except Exception as e:
        if qMessageBox is None:
            syslogger.error("Invalid project file {0}\n{1}".format(fname, e))
        else:
            qMessageBox.critical(
                None, "Cannot load project",
                "Invalid project file {0}\n{1}".format(fname, e))
        return

    if restore_perspective:
        restore_perspective(configProject)
    dataTree = config.get(configProject, 'Root', 'tree', [])
    if not dataTree:
        syslogger.error("No valid data tree specified in this project file")
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

    # cwd = os.getcwd()
    os.chdir(os.path.dirname(fname))
    if csi.model is not None:
        items = csi.model.importData(dataTree, configData=configProject)
    else:
        items = root.insert_data(dataTree, configData=configProject)
        ctr.connect_combined(items, root)
        ctr.run_transforms(items, root)
    root.init_colors(items)
    # os.chdir(cwd)  # don't! This breaks file list update by data selection


def save_project(fname, save_perspective=None):
    configProject = config.ConfigParser(allow_no_value=True)
    configProject.optionxform = str  # makes it case sensitive

    config.put(
        configProject, 'ParSeq Application', 'pipelineName', csi.pipelineName)
    config.put(configProject, 'ParSeq Application', 'appPath', csi.appPath)
    config.put(
        configProject, 'ParSeq Application', 'appVersion', csi.appVersion)
    config.put(
        configProject, 'ParSeq Application', 'appSynopsis', csi.appSynopsis)

    root = csi.dataRootItem
    config.put(configProject, 'Root', 'tree', repr(root))
    config.put(configProject, 'Root', 'groups', str(len(root.get_groups())))
    config.put(configProject, 'Root', 'items', str(len(root.get_items())))

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
    os.chdir(os.path.dirname(fname))
    with open(fname, 'w+', encoding=encoding) as cf:
        configProject.write(cf)


def save_data(fname, saveNodes, saveTypes, qMessageBox=None):
    os.chdir(os.path.dirname(fname))
    if fname.endswith('.pspj'):
        fname = fname.replace('.pspj', '')

    plots = []
    if ('txt' in saveTypes) or ('txt.gz' in saveTypes):
        for iNode, ((nodeName, node), saveNode) in enumerate(
                zip(csi.nodes.items(), saveNodes)):
            if not saveNode:
                continue
            if node.plotDimension == 1:
                header = [node.plotXArray] + [y for y in node.plotYArrays if
                                              not node.get_prop(y, 'abscissa')]
            else:
                continue

            curves = {}
            for it in csi.selectedItems:
                dataToSave = []
                try:
                    x = getattr(it, node.plotXArray)
                except AttributeError:
                    continue
                for aN, aDict in node.arrays.items():
                    role = node.get_prop(aN, 'role')
                    if role == '0D':
                        continue
                    if 'abscissa' in aDict:
                        continue
                    try:
                        d = getattr(it, aN)
                    except AttributeError:
                        continue
                    for trWidget in node.widget.transformWidgets:
                        if ((aN in node.plotYArrays) and
                                hasattr(trWidget, 'extraPlotTransform')):
                            x, d = trWidget.extraPlotTransform(
                                it, node.plotXArray, x, aN, d)
                    dataToSave.append(d)
                dataToSave = [d for d in dataToSave if d is not None]

                headerAll = list(header)
                plotPropsAll = it.plotProps[node.name]
                for fit in csi.fits.values():
                    if fit.node is node:
                        fitAttrName = fit.dataAttrs['fit']
                        try:
                            fity = getattr(it, fitAttrName)
                            dataToSave.append(fity)
                            headerAll.append(fitAttrName)
                            plotPropsAll[fitAttrName] = fit.plotParams['fit']
                        except AttributeError:
                            continue

                nname = nodeName.translate(chars2removeMap)
                dname = it.alias.translate(chars2removeMap)
                sname = u'{0}-{1}-{2}'.format(iNode+1, nname, dname)
                # for iid, d in enumerate(dataToSave):
                #     print(node.name, iid, d.shape)
                dataToSaveSt = np.column_stack(dataToSave)
                if 'txt' in saveTypes:
                    np.savetxt(sname+'.txt', dataToSaveSt,
                               fmt='%.12g', header=' '.join(headerAll))
                if 'txt.gz' in saveTypes:
                    np.savetxt(sname+'.txt.gz', dataToSaveSt,
                               fmt='%.12g', header=' '.join(headerAll))

                curves[sname] = [it.alias, it.color, headerAll, plotPropsAll]

                extrasToSave = [(aDict['abscissa'], aN) for aN, aDict
                                in node.arrays.items() if 'abscissa' in aDict]
                for iG, aG in enumerate(node.auxArrays + extrasToSave):
                    dataAux, headerAux = [], []
                    for yN in aG:
                        try:
                            dataAux.append(getattr(it, yN))
                        except AttributeError:
                            break
                        headerAux.append(yN)
                    if len(dataAux) == 0:
                        continue
                    if iG < len(node.auxArrays):
                        suff = 'aux{0}'.format(iG)
                    else:
                        suff = '{0}'.format(aG[1])
                    sname = u'{0}-{1}-{2}-{3}'.format(
                        iNode+1, nname, dname, suff)
                    if 'txt' in saveTypes:
                        np.savetxt(sname+'.txt', np.column_stack(dataAux),
                                   fmt='%.12g', header=' '.join(headerAux))
                    if 'txt.gz' in saveTypes:
                        np.savetxt(sname+'.txt.gz', np.column_stack(dataAux),
                                   fmt='%.12g', header=' '.join(headerAux))
                    curves[sname] = [it.alias, it.color, headerAux]

            if 'txt' in saveTypes:
                plots.append(['txt', node.name, node.plotDimension,
                              node.widget.getAxisLabels(), curves])
            if 'txt.gz' in saveTypes:
                plots.append(['txt.gz', node.name, node.plotDimension,
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
                header = [node.plotXArray] + [y for y in node.plotYArrays if
                                              not node.get_prop(y, 'abscissa')]
            elif node.plotDimension == 2:
                header = [node.plot2DArray]
            elif node.plotDimension == 3:
                header = [node.plot3DArray]

            curves = {}
            for it, sname in zip(csi.selectedItems, snames):
                if node.plotDimension == 1:
                    try:
                        x = getattr(it, node.plotXArray)
                    except AttributeError:
                        continue
                for aN, aDict in node.arrays.items():
                    if 'abscissa' in aDict:
                        continue
                    try:
                        d = getattr(it, aN)
                    except AttributeError:
                        continue
                    for trWidget in node.widget.transformWidgets:
                        if (node.plotDimension == 1 and
                            (aN in node.plotYArrays) and
                                hasattr(trWidget, 'extraPlotTransform')):
                            x, d = trWidget.extraPlotTransform(
                                it, node.plotXArray, x, aN, d)
                    dataToSave[it][aN] = d.tolist() if d is not None else None

                extrasToSave = [(aDict['abscissa'], aN) for aN, aDict
                                in node.arrays.items() if 'abscissa' in aDict]
                for aN in [j for i in (node.auxArrays + extrasToSave)
                           for j in i]:
                    try:
                        d = getattr(it, aN)
                    except AttributeError:
                        continue
                    dataToSave[it][aN] = d.tolist() if d is not None else None

                headerAll = list(header)
                plotPropsAll = it.plotProps[node.name]
                for fit in csi.fits.values():
                    if fit.node is node:
                        fitAttrName = fit.dataAttrs['fit']
                        try:
                            fity = getattr(it, fitAttrName)
                            dataToSave[it][fitAttrName] = fity.tolist()
                            headerAll.append(fitAttrName)
                            plotPropsAll[fitAttrName] = fit.plotParams['fit']
                        except AttributeError:
                            continue

                curves[sname] = [it.alias, it.color, headerAll, plotPropsAll]
                if node.auxArrays + extrasToSave:
                    headerAux = []
                    for aG in (node.auxArrays + extrasToSave):
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
                header = [node.plotXArray] + [y for y in node.plotYArrays if
                                              not node.get_prop(y, 'abscissa')]
            elif node.plotDimension == 2:
                header = [node.plot2DArray]
            elif node.plotDimension == 3:
                header = [node.plot3DArray]

            curves = {}
            for it, sname in zip(csi.selectedItems, snames):
                if node.plotDimension == 1:
                    try:
                        x = getattr(it, node.plotXArray)
                    except AttributeError:
                        continue
                for aN, aDict in node.arrays.items():
                    if 'abscissa' in aDict:
                        continue
                    try:
                        y = getattr(it, aN)
                        for trWidget in node.widget.transformWidgets:
                            if (node.plotDimension == 1 and
                                (aN in node.plotYArrays) and
                                    hasattr(trWidget, 'extraPlotTransform')):
                                x, y = trWidget.extraPlotTransform(
                                    it, node.plotXArray, x, aN, y)
                        dataToSave[it][aN] = y
                    except AttributeError:
                        continue

                extrasToSave = [(aDict['abscissa'], aN) for aN, aDict
                                in node.arrays.items() if 'abscissa' in aDict]
                for aN in [j for i in (node.auxArrays + extrasToSave)
                           for j in i]:
                    try:
                        dataToSave[it][aN] = getattr(it, aN)
                    except AttributeError:
                        continue

                headerAll = list(header)
                plotPropsAll = it.plotProps[node.name]
                for fit in csi.fits.values():
                    if fit.node is node:
                        fitAttrName = fit.dataAttrs['fit']
                        try:
                            fity = getattr(it, fitAttrName)
                            dataToSave[it][fitAttrName] = fity
                            headerAll.append(fitAttrName)
                            plotPropsAll[fitAttrName] = fit.plotParams['fit']
                        except AttributeError:
                            continue

                curves[sname] = [it.alias, it.color, headerAll, plotPropsAll]
                if node.auxArrays + extrasToSave:
                    headerAux = []
                    for aG in (node.auxArrays + extrasToSave):
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
            with h5py.File(fname+'.h5', 'w', track_order=True) as f:
                # the global `track_order=True` does not work
                dataGrp = f.create_group('data', track_order=True)
                plotsGrp = f.create_group('plots', track_order=True)
                for it in csi.selectedItems:
                    dname = it.alias.translate(chars2removeMap)
                    if dname in f:
                        continue
                    grp = dataGrp.create_group(dname, track_order=True)
                    for aN in dataToSave[it]:
                        if aN in grp:
                            continue
                        if dataToSave[it][aN] is None:  # when optional
                            continue
                        com = None if np.isscalar(dataToSave[it][aN]) else\
                            'gzip'
                        grp.create_dataset(aN, data=dataToSave[it][aN],
                                           compression=com)
                    grp.create_dataset('transformParams',
                                       data=str(it.transformParams))
                # syslogger.info('data keys:', dataGrp.keys())
                for plot in h5plots:
                    gname = plot[0].translate(chars2removeMap)
                    grp = plotsGrp.create_group(gname, track_order=True)
                    grp.create_dataset('ndim', data=plot[1])
                    grp.create_dataset('axes', data=str(plot[2]))
                    grp.create_dataset('plots', data=str(plot[3]))
        except Exception as e:
            if qMessageBox is None:
                syslogger.error("Cannot write file {0}".format(fname))
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
        syslogger.error("no plots selected")
        return
    if fname.endswith('.pspj'):
        fname = fname.replace('.pspj', '')
    basefname = os.path.basename(fname)

    pyExportMod = os.path.join(__fdir__, 'plotExport.py')
    with open(pyExportMod, 'r') as f:
        lines = [line.rstrip('\n') for line in f]

    output = lines[:2]
    now = datetime.datetime.now()
    header = '"""This script was created by ParSeq v{0} on {1}"""'.format(
        __version__, now.strftime('%Y-%m-%d %H:%M:%S'))
    output.extend([header])

    if lib == 'mpl':
        output.extend(lines[1:3])

    output.extend(_script(lines, "readFile"))
    dims = set([plot[2] for plot in plots] + [plot[1] for plot in h5plots])
    for dim in [1, 2, 3]:
        if dim in dims:
            output.extend(_script(lines, "read{0}D".format(dim)))
            output.extend(_script(lines, "plot{0}D{1}".format(dim, lib)))

    if len(h5plots) > 0:
        output.extend(_script(lines, "getPlotsFromHDF5"))

    if lib == 'mpl':
        output.extend(_script(lines, "plotSavedDataMpl"))
    elif lib == 'silx':
        output.extend(_script(lines, "plotSavedDataSilx"))

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

    if lib == 'mpl':
        output.extend(["    plotSavedDataMpl(plots)", ""])
    elif lib == 'silx':
        output.extend(["    from silx.gui import qt",
                       "    app = qt.QApplication([])",
                       "    plotSavedDataSilx(plots)",
                       "    app.exec_()", ""])

    fnameOut = '{0}_{1}.py'.format(fname, lib)
    os.chdir(os.path.dirname(fname))
    with open(fnameOut, 'w', encoding=encoding) as f:
        f.write('\n'.join(output))

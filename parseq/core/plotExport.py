# -*- coding: utf-8 -*-
"This script was created by ParSeq."

import matplotlib.pyplot as plt


def readFile(saveType, fname):
    h5file = None
    if saveType.endswith('txt'):
        import numpy as np
        arrays = np.loadtxt(fname+'.txt')
        return arrays
    if saveType.endswith('txt.gz'):
        import numpy as np
        arrays = np.loadtxt(fname+'.txt.gz')
        return arrays
    elif saveType.endswith('json'):
        import json
        with open(fname+'.json', 'r') as f:
            data = json.load(f)
    elif saveType.endswith('pickle'):
        import pickle
        with open(fname+'.pickle', 'rb') as f:
            data = pickle.load(f)
    elif saveType.endswith('h5'):
        import h5py
        if '::/' in fname:
            filename, h5path = fname.split('::/')
        else:
            filename, h5path = saveType, fname
        h5file = h5py.File(filename, 'r')
        data = h5file[h5path]
    return data, h5file  # end readFile


def read1D(saveType, fname, props):
    curves = []
    headers = props[2][1:]
    if saveType.endswith(('txt', 'txt.gz')):
        arrays = readFile(saveType, fname)
        x = arrays[:, 0]
        ys = [arrays[:, iy+1] for iy in range(arrays.shape[1]-1)]
        curves.append([x, ys, headers])
    elif saveType.endswith(('json', 'pickle', 'h5')):
        data, h5file = readFile(saveType, fname)
        # slicing is needed to create an ndarray from HDF5 object
        x = data[props[2][0]][:]
        ys = [data[prop][:] for prop in headers]
        curves.append([x, ys, headers])
        if len(props) > 4:  # auxArrays
            auxs = props[4]
            for aux in auxs:
                xa = data[aux[0]][:]
                headeras = aux[1:]
                yas = [data[prop][:] for prop in headeras]
                curves.append([xa, yas, headeras])
        if h5file is not None:
            h5file.close()
    return curves  # end read1D


def plot1Dmpl(nodeData):
    saveType = nodeData[0]
    fig = plt.figure()
    fig.suptitle(nodeData[1] + ' ' + saveType)
    axl = fig.add_subplot(111)
    axl.set_xlabel(nodeData[3][0])
    axl.set_ylabel(nodeData[3][1])
    if nodeData[3][2]:
        axr = axl.twinx()
        axr.set_ylabel(nodeData[3][2])

    savedColumns = nodeData[4]
    for fname, props in savedColumns.items():
        curves = read1D(saveType, fname, props)
        if len(props) > 3:
            yprops = props[3]
            clr = props[1]

        for curve in curves:
            x, ys, headers = curve
            for y, header in zip(ys, headers):
                try:
                    kw = dict(yprops[header])
                except KeyError:
                    kw = {}
                    clr = 'gray'
                yaxis = kw.pop('yaxis', 'left')
                if 'symbolsize' in kw:
                    ms = kw.pop('symbolsize')
                    kw['markersize'] = ms
                if 'symbol' in kw:
                    m = kw.pop('symbol')
                    kw['marker'] = m
                lbl = props[0] + '.' + header
                ax = axl if yaxis.startswith('l') else axr
                ax.plot(x, y, color=clr, label=lbl, **kw)
    ax.legend()
    # fig.savefig('test.png')
    # end plot1Dmpl


def plot1Dsilx(nodeData):
    from silx.gui.plot import Plot1D

    saveType = nodeData[0]
    plot = Plot1D()
    plot.setGraphTitle(nodeData[1] + ' ' + saveType)
    plot.setGraphXLabel(label=nodeData[3][0])
    plot.setGraphYLabel(label=nodeData[3][1], axis='left')
    if nodeData[3][2]:
        plot.setGraphYLabel(label=nodeData[3][2], axis='right')

    savedColumns = nodeData[4]
    for fname, props in savedColumns.items():
        curves = read1D(saveType, fname, props)
        if len(props) > 3:
            yprops = props[3]
            clr = props[1]

        for curve in curves:
            x, ys, headers = curve
            for y, header in zip(ys, headers):
                try:
                    kw = dict(yprops[header])
                except KeyError:
                    kw = {'yaxis': 'left'}
                    clr = 'gray'
                symbolsize = kw.pop('symbolsize', 2)
                symbol = kw.get('symbol', None)
                lbl = props[0] + '.' + header
                plot.addCurve(x, y, color=clr, legend=lbl, **kw)
                if symbol is not None:
                    curve = plot.getCurve(lbl)
                    if curve is not None:
                        curve.setSymbolSize(symbolsize)

    plot.show()
    return plot  # end plot1Dsilx


def read2D(saveType, fname, props):
    maps = []
    if saveType.endswith(('json', 'pickle', 'h5')):
        data, h5file = readFile(saveType, fname)
        # slicing is needed to create an ndarray from HDF5 object
        z = data[props[2]][:]
        maps.append(z)
        if h5file is not None:
            h5file.close()
    return maps  # end read2D


def plot2Dmpl(nodeData):
    saveType = nodeData[0]
    savedColumns = nodeData[4]
    for fname, props in savedColumns.items():
        maps = read2D(saveType, fname, props)

    # applied only to one 2D map:
    fig = plt.figure()
    fig.suptitle(nodeData[1] + ' ' + saveType)
    axl = fig.add_subplot(111)
    axl.set_xlabel(nodeData[3][0])
    axl.set_ylabel(nodeData[3][1])
    axl.imshow(maps[0], origin='lower', aspect='auto')
    # fig.savefig('test.png')
    # end plot2Dmpl


def plot2Dsilx(nodeData):
    from silx.gui.plot import Plot2D
    from silx.gui import colors

    saveType = nodeData[0]
    savedColumns = nodeData[4]
    for fname, props in savedColumns.items():
        maps = read2D(saveType, fname, props)

    # applied only to one 2D map:
    plot = Plot2D()
    plot.setGraphTitle(nodeData[1] + ' ' + saveType)
    plot.getXAxis().setLabel(label=nodeData[3][0])
    plot.getYAxis().setLabel(label=nodeData[3][1])
    xOrigin, xScale = 0, 1
    yOrigin, yScale = 0, 1
    plot.addImage(maps[0], colormap=colors.Colormap('viridis'),
                  origin=(xOrigin, yOrigin), scale=(xScale, yScale))
    # plot.saveGraph('test.png')
    plot.show()
    return plot  # end plot2Dsilx


def read3D(saveType, fname, props):
    maps = []
    if saveType.endswith(('json', 'pickle', 'h5')):
        data, h5file = readFile(saveType, fname)
        # slicing is needed to create an ndarray from HDF5 object
        v = data[props[2]][:]
        maps.append(v)
        if h5file is not None:
            h5file.close()
    return maps  # end read3D


def plot3Dmpl(nodeData, level=0.4):
    import numpy as np

    saveType = nodeData[0]
    savedColumns = nodeData[4]
    for fname, props in savedColumns.items():
        maps = read3D(saveType, fname, props)

    # applied only to one (first) 3D map:
    fig = plt.figure()
    fig.suptitle(nodeData[1] + ' ' + saveType)
    ax = fig.add_subplot(projection='3d')
    ax.set_xlabel(nodeData[3][0])
    ax.set_ylabel(nodeData[3][1])
    ax.set_zlabel(nodeData[3][2])
    v = maps[0]
    v = v / v.max()
    x = np.linspace(0, v.shape[0]-1, v.shape[0])
    y = np.linspace(0, v.shape[1]-1, v.shape[1])
    z = np.linspace(0, v.shape[2]-1, v.shape[2])
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    X = X[v > level]
    Y = Y[v > level]
    Z = Z[v > level]
    v = v[v > level]
    ax.scatter(X, Y, Z, c=v, s=v*10, cmap='viridis')
    # fig.savefig('test.png')
    # end plot3Dmpl


def plot3Dsilx(nodeData):
    from silx.gui.plot import StackView

    saveType = nodeData[0]
    plot = StackView()
    plot.setColormap('viridis')
    plot.setGraphTitle(nodeData[1] + ' ' + saveType)
    plot.setLabels(nodeData[3])

    savedColumns = nodeData[4]
    for fname, props in savedColumns.items():
        maps = read3D(saveType, fname, props)

    # applied only to one (first) 3D map:
    v = maps[0]
    plot.setStack(v)
    # plot.saveGraph('test.png')
    plot.show()
    return plot  # end plot3Dsilx


def getPlotsFromHDF5(path):
    import h5py

    h5file = h5py.File(path, 'r')
    plotGrp = h5file['plots']
    plots = []
    for key in plotGrp.keys():
        ndim = plotGrp[key]['ndim'][()]
        axes = eval(plotGrp[key]['axes'][()])
        curves = eval(plotGrp[key]['plots'][()])
        plots.append([path, key, ndim, axes, curves])
    return(plots)  # end getPlotsFromHDF5


def plotSavedData(plots, lib='mpl'):
    global widgets
    widgets = []
    for nodeData in plots:
        ndim = nodeData[2]
        plotFunc = globals()['plot{0}D{1}'.format(ndim, lib)]
        widgets.append(plotFunc(nodeData))  # to keep references to silx polots
    if lib == 'mpl':
        plt.show()  # end plotSavedData


if __name__ == '__main__':
    h5name = r'c:\ParSeq\Scripts\aaa.h5'
    plots = getPlotsFromHDF5(h5name)

    # lib = 'silx'
    lib = 'mpl'
    if lib == 'silx':
        from silx.gui import qt
        app = qt.QApplication([])
        plotSavedData(plots, 'silx')
        app.exec_()
    elif lib == 'mpl':
        plotSavedData(plots, 'mpl')

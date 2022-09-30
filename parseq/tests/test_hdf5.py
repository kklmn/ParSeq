# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

#from silx.gui import qt

import os.path as osp
import sys; sys.path.append('../..')  # analysis:ignore
import numpy as np
import h5py
from silx.gui.data.DataViewerFrame import DataViewerFrame
from silx.gui import qt
crop = 0, 0, 1555, 515


def write_avi(fName):
    import cv2

    fPath = osp.join('../../_data_big', fName+'.hdf5')
    f = h5py.File(fPath, 'r')
#    data = 'und_energy'
#    e = f[data][:]
    data = 'i0'
    i0 = f[data][:]
    data = 'lambdaOne_images'
    images = f[data][:len(i0), :, :]
    print('shape = {0}'.format(images.shape))
    nFrames = len(i0)

    maxInTime = 0
    for i in range(nFrames):
        frame = np.array(f[data][i, crop[1]: crop[3]+1, crop[0]: crop[2]+1])
        maxFrame = np.max(frame)
        if maxInTime < maxFrame:
            maxInTime = maxFrame
    print(maxInTime)

    frameSize = crop[2]-crop[0]+1, crop[3]-crop[1]+1
    print(frameSize)
    fps = 10
    writer = cv2.VideoWriter(fName + '.mp4', -1, fps, frameSize, isColor=0)
    for i in range(nFrames):
        print("{0} of {1}".format(i+1, nFrames))
        frame = np.array(f[data][i, crop[1]: crop[3]+1, crop[0]: crop[2]+1],
                         dtype=float) * 1e6
        frame *= 255. / maxInTime
        frameOut = np.array(frame, dtype='>u1')
        writer.write(frameOut)
    f.close()


def showInWidget(fName):
    fPath = osp.join('../../_data_big', fName+'.hdf5')
    f = h5py.File(fPath, 'r')
#    data = 'und_energy'
#    e = f[data][:]
    data = 'i0'
    i0 = f[data][:]
    data = 'lambdaOne_images'
    images = f[data][:len(i0), :, :]
    print('shape = {0}'.format(images.shape))

    app = qt.QApplication(sys.argv)
    viewer = DataViewerFrame()
    frames = f[data][:, crop[1]: crop[3]+1, crop[0]: crop[2]+1]
    maxInTime = frames.max()
    frames = np.array(frames * 1e6 * 255. / maxInTime, dtype='>u1')
    viewer.setData(frames)
    viewer.setVisible(True)
    viewer.show()
    app.exec_()

    f.close()


if __name__ == '__main__':
    write_avi('cuo_rxes_0001')
    # write_avi('cu2o_rxes_0001')

    # showInWidget('cu2o_rxes_0001')
    print("Done")

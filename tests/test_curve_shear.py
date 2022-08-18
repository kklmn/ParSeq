# -*- coding: utf-8 -*-
"""
Created on Mon Aug  1 10:43:22 2022

@author: konkle
"""

import numpy as np
from scipy import interpolate

import cv2 as cv
import matplotlib.pyplot as plt
from skimage.transform import warp

fname_in = 'circles.png'
fname_out = 'circles-rect.png'


def create_test_image():
    img = np.zeros((480, 640, 3), np.uint8)
    for i in range(7):
        color = np.random.randint(256, size=3)
        cv.circle(img, (2000+100*i, 700), 2000, color.tolist(), -1)
    for i in range(7):
        cv.line(img, (i*100, 0), (i*100-50, 511), (255, 0, 0), 5)
    cv.imshow('img', img)
    cv.imwrite(fname_in, img)


def make_curve_shear(vertices, length):
    f, _ = interpolate.splprep(np.array(vertices).T, s=0)
    xint, yint = interpolate.splev(np.linspace(0, 1, length), f)
    return xint - xint.min(), xint, yint


def rectify_image(image, shear):
    def shift_left(xy):
        xy[:, 0] += shear[xy[:, 1].astype(int)]
        return xy

    out = warp(image, shift_left)
    return out


def process_and_plot():
    image = cv.cvtColor(cv.imread(fname_in), cv.COLOR_BGR2RGB)
    vertices = [(426., 0.), (377, 150), (335, 330), (312, 479.)]
    shear, xint, yint = make_curve_shear(vertices, image.shape[0])
    rimage = rectify_image(image, shear)
    cv.imwrite(fname_out, cv.cvtColor(
        (rimage*255).astype(np.uint8), cv.COLOR_RGB2BGR))

    fig = plt.figure(figsize=(14, 5))

    ax1 = fig.add_subplot(121)
    ax1.imshow(image, origin='upper', aspect='auto')
    xs, ys = zip(*vertices)
    ax1.plot(xs, ys, 's', lw=2, color='m', ms=10)
    ax1.plot(xint, yint, '-r', lw=3)

    ax2 = fig.add_subplot(122)
    ax2.imshow(rimage, origin='upper', aspect='auto')

    plt.show()


if __name__ == '__main__':
    # create_test_image()
    process_and_plot()

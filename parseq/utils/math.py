# -*- coding: utf-8 -*-
r"""
Data combinations
-----------------

The following data combinations are available: average, sum, RMS deviation, and
only for 1D: classical PCA, cumulative PCA, target transformation and
MCR-ALS. If the abscissas of the involved 1D datasets differ, interpolation can
be optionally applied. These operations are performed on all arrays defined in
the `node.arrays` dictionary and result in the creation of one or more new
datasets.

Average, sum, rms deviation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

These combinations generate a single new data item from multiple user-selected
datasets.

PCA: classic and cumulative
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user specifies a 1D array name for PCA analysis. These arrays from
:math:`n` selected data items may have different lengths. In such cases, they
are interpolated onto the abscissa grid of the first selected dataset. The
:math:`n` arrays form an :math:`m×n` data matrix
:math:`D = \begin{bmatrix} \mathbf{d}_1 & \mathbf{d}_2 & \dots & \mathbf{d}_n
\end{bmatrix}`.

For the covariance matrix :math:`D^TD`, the eigenvalues :math:`\lambda_j` and
corresponding eigenvectors :math:`\mathbf{e}_j` are computed and sorted in
descending order of :math:`\lambda_j` with :math:`\lambda_1` being the largest.
The following identity always holds:
:math:`\sum_{j=1}^n \mathbf{e}_j \mathbf{e}_j^T = \mathbf{1}`.

If only :math:`N<n` data vectors are linearly independent, the sum can be
truncated at :math:`j=N`, while still satisfying
:math:`\sum_{j=1}^N \mathbf{e}_j \mathbf{e}_j^T = \mathbf{1}`.
In this case :math:`\lambda_j=0` for all :math:`j > N`. In practice, truncation
is applied such that :math:`D\sum_{j=1}^{N}\mathbf{e}_j\mathbf{e}^T_j`
reproduces :math:`D` within the noise level. Equivalently, the discarded
contribution :math:`D\sum_{j=N+1}^{n}\mathbf{e}_j \mathbf{e}^T_j` remains
within the noise.

ParSeq does not currently provide dedicated tools for estimating noise levels.
Consequently, direct comparison of the truncated contribution with the noise is
not implemented as a general feature. Instead, (a) the scree plot and (b)
Malinowski’s IND function [IND]_ are provided to assist in determining
the appropriate value of :math:`N`.

The data matrix admits two PCA representations:

.. math::
    D_{\rm PCA-classic}(k) = D\mathbf{e}_k \mathbf{e}^T_k

.. math::
    D_{\rm PCA-cumulative}(k) = D\sum_{j=1}^{k} \mathbf{e}_j \mathbf{e}^T_j

Here, :math:`(k)` denotes the :math:`k`\ th principal component. In both
representations, the first PCA component is the average of all spectra.
Subsequent components represent deviations from this average: in the classical
PCA, each component describes an individual deviation mode, whereas in the
cumulative PCA, the components represent progressively accumulated deviations
added to the average.

.. [IND] E R Malinowski, Anal. Chem. **49** (1977) 606.

Target transformation
~~~~~~~~~~~~~~~~~~~~~

From :math:`n` selected basis (reference) 1D datasets, an :math:`m×n` basis
matrix is constructed:
:math:`B = \begin{bmatrix} \mathbf{d}_1 & \mathbf{d}_2 & \dots & \mathbf{d}_n
\end{bmatrix}`. If the array length :math:`m` differs among the :math:`n` basis
spectra, they are interpolated to match the grid of the first dataset.

If the basis spectra are linearly independent then the covariance matrix
:math:`B^TB` (of size :math:`n×n`) has full rank :math:`n` and its inverse
:math:`(B^TB)^{-1}` exists. The matrix :math:`B(B^TB)^{-1}B^T` is an orthogonal
projector onto the subspace spanned by the basis spectra, since it is
idempotent (equal to its square). Consequently, a spectrum :math:`\mathbf{d}`
belongs to this subspace if and only if
:math:`B(B^TB)^{-1}B^T\mathbf{d}=\mathbf{d}`.

In practice, one verifies whether :math:`B(B^TB)^{-1}B^T\mathbf{d}` reproduces
:math:`\mathbf{d}` within the noise level. In ParSeq, the inverse covariance
matrix is computed via the eigenvalues :math:`\lambda_j` and eigenvectors
:math:`\mathbf{e}_j` of :math:`B^TB`:
:math:`(B^TB)^{-1} = \sum_j\lambda_j^{-1}\mathbf{e}_j\mathbf{e}^T_j`. This
approach also enables inspection of the eigenvalues to assess the linear
independence of the basis spectra.

MCR-ALS
~~~~~~~

.. imagezoom:: _images/MCR0.png
   :alt: &ensp;70 XANES spectra during gas switching.
   :align: right

The Multivariate Curve Resolution–Alternating Least Squares (MCR-ALS) method
[ALS]_ enables the decomposition (with potentially many valid solutions) of an
:math:`m×n` data matrix :math:`D` into the product of :math:`N` basic
components collected in the matrix :math:`S` (:math:`m×N`) and :math:`N`
concentration profiles collected in the matrix :math:`C` (:math:`n×N`):

.. imagezoom:: _images/PCA.png
   :align: left
   :alt: &ensp;Eigenvalue analysis of 70 XANES spectra during gas switching.

.. math::
    D = SC^T
    :label: ALS

This section describes the ParSeq implementation of MCR-ALS.

The first step is to determine the number of basic components, :math:`N`. This
can be guided by examining the scree plot and Malinowski's IND function. In
practice, however, these methods often do not yield a definitive result, and
the value of :math:`N` is typically guessed.

The second step is to obtain an initial estimate of :math:`S`. Often, one
component (i.e., one column of :math:`S`) is known from the sample history and
can be taken as either the initial or the final spectrum in a measurement
series. The remaining columns can be determined by identifying spectra that
exhibit the largest deviation from the components already defined. This is
achieved by subtracting the target transformation of :math:`D` from :math:`D`
and selecting the column with the largest norm. That column of :math:`D` is
then used as the next initial column of :math:`S`.

The next stage consists of two alternating matrix transformations that are
applied iteratively to compute:
(a) :math:`C` from :math:`D` and :math:`S`, according to the transposed
Eq. :math:numref:`ALS` and
(b) :math:`S` from :math:`D` and :math:`C`, according to Eq. :math:numref:`ALS`.
The transformations are given by :math:`C = D^TS(S^TS)^{-1}` and
:math:`S = DC(C^TC)^{-1}`.
After each transformation, common constraints are enforced: non-negativity of
:math:`C` and optionally :math:`S`, and mass balance (i.e. the sum of each row
of :math:`C` equals 1). Additionally, prior to applying the mass balance
constraint, lower and/or upper bounds may be imposed on individual columns of
:math:`C`. These alternating transformations are repeated until convergence is
achieved. If :math:`S^TS` or :math:`C^TC` becomes singular, the iterative
scheme fails to converge to a solution.

The final step is to estimate the uncertainties in :math:`C`. One possible
approach is to perform linear combination fitting (LCF) using the obtained
:math:`S` as the basis set. However, the fit quality is typically dominated by
systematic uncertainties, which leads to a significant underestimation of the
error bars. This functionality is still under development in ParSeq.

The figures in this section present an example of MCR-ALS applied to a series
of operando spectra of a Ni-containing catalyst, measured in a capillary cell
at the Balder/MAX-IV beamline during gas switching [Ni-MCR-ALS]_. The dataset
consists of 70 XANES spectra showing subtle variations in both the edge
position and the white-line region.

The scree plot and Malinowski’s IND function suggest that the number of
independent components is 3. This would imply transitions between two main
states with a third, likely transient, intermediate state. However, the ALS
analysis does not yield a physically meaningful concentration profile
:math:`C_3` and a well-defined component :math:`S_3`. Notably, there is a
large difference spanning several orders of magnitude between the first and
second eigenvalues, see the scree plot above, while the gap between the second
and third is much smaller. This indicates that the second and third components
are not well separated. Consequently, the number of independent components was
set to 2.

.. imagezoom:: _images/MCRS.png
   :align: left
   :alt: &ensp;MCR-ALS of 70 XANES spectra during gas switching. S matrix.

.. imagezoom:: _images/MCRC.png
   :align: right
   :alt: &ensp;MCR-ALS of 70 XANES spectra during gas switching. C matrix.

The solutions for :math:`S` and :math:`C` are not unique, as illustrated by the
accompanying figures. In this example, a low-pass constraint is applied to
:math:`C_2` ​. Varying this constraint leads to different solutions for both
:math:`C` and :math:`S`. One might expect that these alternative solutions
could be distinguished by the norm of the residual :math:`D - SC^T`. However,
this norm is typically orders of magnitude smaller than the noise level, making
all such solutions effectively equivalent in terms of fit quality. Therefore,
selecting the most appropriate solution requires additional chemical or
physical insight beyond the mathematical decomposition.

If the ALS solution is not unique, does it still have value? In the
two-dimensional space defined by basic spectra and their concentrations, all
admissible points are *a priori* valid solutions. The MCR-ALS method reduces
this space to a one-dimensional manifold (a line). If this line intersects
known reference spectra, the interpretation becomes straightforward, and the
method is clearly valuable. Even when the resulting components :math:`S` do not
resemble any known reference spectra, further discrimination may still be
possible using computational spectroscopy or other complementary techniques.
Thus, even a continuum of possible solutions can provide meaningful insight and
may still be scientifically valuable and publishable.

The shown example can be scrutinized by running the script
``parseq/tests/test_MCRWidget.py`` and/or by loading the ParSeq-XAS project
file ``parseq_XAS/saved/mcr.pspj``.

.. [ALS] A de Juan, J Jaumot and R Tauler, Anal. Methods, **6** (2014) 4964.
.. [Ni-MCR-ALS] N Kosinov (2026) unpublished, private communication.


"""
__author__ = "Konstantin Klementiev"
__date__ = "9 Jun 2026"
# !!! SEE CODERULES.TXT !!!

import numpy as np
# from scipy.interpolate import UnivariateSpline
from scipy.interpolate import make_interp_spline, PPoly, interp1d
from scipy.signal import savgol_filter
import scipy.linalg as spl
from scipy.optimize import curve_fit


def line(xs, ys):
    try:
        k = (ys[1] - ys[0]) / (xs[1] - xs[0])
    except ZeroDivisionError:
        return np.inf, 0.
    b = ys[1] - k*xs[1]
    return k, b


def fwhm(x, y):
    # simple implementation, quantized by dx:
    def simple():
        topHalf = np.where(y >= 0.5*np.max(y))[0]
        if len(topHalf) == 0:
            return 0
        return np.abs(x[topHalf[0]] - x[topHalf[-1]])

    # a better implementation, weakly dependent on dx size
    try:
        if x[0] > x[-1]:
            x, y = x[::-1], y[::-1]
        # spline = UnivariateSpline(x, y - y.max()*0.5, s=0)
        # roots = spline.roots()
        spline = make_interp_spline(x, y - y.max()*0.5)
        roots = PPoly.from_spline(spline, False).roots()
        return max(roots) - min(roots)
    except ValueError:
        return simple()


def smooth_convolve(y, npoints):
    """Array smoothing, slow."""
    w = np.ones(npoints, 'd')
    return np.convolve(w/w.sum(), y, mode='same')


def smooth_cumsum(y, npoints):
    """In-place smoothing, a replacement for np.convolve that is pretty slow.
    Based on https://stackoverflow.com/a/34387987/2696065"""
    cs = np.cumsum(np.insert(y, 0, 0))
    ns = 2*npoints + 1
    res = np.array(y)
    res[npoints: -npoints] = (cs[ns:] - cs[:-ns]) / ns
    return res  # same shape as y


def smooth_savgol(y, npoints):
    """*npoints* must be > 3 (polyniomial order)"""
    return savgol_filter(y, max(npoints, 4), 3)  # polynomial order 3


def get_roi_mask(geom, xs, ys):
    if geom['kind'] == 'RectangleROI':
        x, y = geom['origin']
        w, h = geom['size']
        return (xs >= x) & (xs <= x+w) & (ys >= y) & (ys <= y+h)
    elif geom['kind'] == 'ArcROI':
        x, y = geom['center']
        r1, r2 = geom['innerRadius'], geom['outerRadius']
        dist2 = (xs-x)**2 + (ys-y)**2
        return (dist2 >= r1**2) & (dist2 <= r2**2)
    elif geom['kind'] == 'BandROI':
        x1, y1 = geom['begin']
        x2, y2 = geom['end']
        k, b = line((x1, x2), (y1, y2))
        w = geom['width']
        return (ys >= k*xs + b - w/2) & (ys <= k*xs + b + w/2)
    elif geom['kind'] == 'HorizontalRangeROI':
        vmin, vmax = geom['vmin'], geom['vmax']
        return (xs >= vmin) & (xs <= vmax) & (ys > 0)
    else:
        raise ValueError('unsupported ROI type')


def interpolate_frames(keyFrameGeometries, ind, wantExtrapolate=True):
    """
    Piecewise linear interpolation between ROI geometries saved as key frames
    for a stacked image.
    *keyFrameGeometries*: dict {key_frame: [list of roi geometries]}, where roi
    geometries are dicts of roi parameters.
    *ind*: int index in the stacking direction
    *wantExtrapolate*: bool, controls the possible hanging ends, when the key
    frames are not at the ends of the stack.
    """
    assert len(keyFrameGeometries) > 1
    keys = list(sorted(keyFrameGeometries.keys()))
    if ind <= keys[0]:
        if wantExtrapolate:
            ikey = 0
        else:
            return keyFrameGeometries[keys[0]]
    elif ind >= keys[-1]:
        if wantExtrapolate:
            ikey = len(keys) - 2
        else:
            return keyFrameGeometries[keys[-1]]
    else:
        for ikey in range(len(keys)-1):
            if keys[ikey] <= ind < keys[ikey+1]:
                break
        else:
            raise ValueError('wrong key frames')

    # linear interpolation between ikey and ikey+1:
    savedRois0 = keyFrameGeometries[keys[ikey]]
    savedRois1 = keyFrameGeometries[keys[ikey+1]]
    rr = (ind-keys[ikey]) / (keys[ikey+1]-keys[ikey])
    res = []
    for savedRoi0, savedRoi1 in zip(savedRois0, savedRois1):
        savedRoi = {k0: v0 if isinstance(v0, (str, bool)) else
                    (np.array(v1)-np.array(v0))*rr + np.array(v0)
                    for (k0, v0), (k1, v1) in zip(
                        sorted(savedRoi0.items()), sorted(savedRoi1.items()))}
        res.append(savedRoi)
    return res


def make_PCA(D, eigvals, get_indicators=False):
    DTD = np.dot(D.T, D)
    DTD /= np.diag(DTD).sum()
    try:
        kweigh = dict(eigvals=eigvals)
        w, v = spl.eigh(DTD, **kweigh)
    except TypeError:  # the kw 'eigvals' is gone
        kweigh = dict(subset_by_index=eigvals)
        w, v = spl.eigh(DTD, **kweigh)
    # rec = np.dot(np.dot(v, np.diag(w)), v.T)
    # print("diff DTD--decomposed(DTD) = {0}".format(np.abs(DTD-rec).sum()))

    if get_indicators:
        cs = w[:-1].cumsum()
        m, n = D.shape
        k = np.arange(1, n)  # up to n-1
        IE = (np.abs(cs[::-1])*k / (m*n*(n-k)))**0.5
        IND = (np.abs(cs[::-1]) / (m*(n-k)))**0.5 / (n-k)**2
        return w, v, IE, IND
    else:
        return w, v


def auto_eigh(D, normalize_trace=False):
    DTD = np.dot(D.T, D)
    if normalize_trace:
        DTD /= np.diag(DTD).sum()
    w, v = spl.eigh(DTD)
    # rec = np.dot(np.dot(v, np.diag(w)), v.T)
    # print("diff DTD--decomposed(DTD) = {0}".format(np.abs(DTD-rec).sum()))
    return w, v


def unlike(B, D, found):
    if B is None:
        col = D[:, 0][:, None]
    else:
        BTB = np.dot(B.T, B)
        w, v = spl.eigh(BTB)
        w[w <= 0] = 1e-20
        revBTB = np.dot(np.dot(v, np.diag(1/w)), v.T)
        BTD = np.dot(B.T, D)
        revBTBBTD = np.dot(revBTB, BTD)
        reduced = D - np.dot(B, revBTBBTD)
        reducedNorms = np.sum(reduced**2, axis=0)
        diffSorted = np.argsort(reducedNorms)[::-1]
        imaxDiff = 0
        while imaxDiff in found:
            imaxDiff += 1
        found.append(imaxDiff)
        maxDiff = diffSorted[imaxDiff]
        # print('maxDiff', maxDiff)
        col = D[:, maxDiff][:, None]
    return col


def initial(x, D, mcrData):
    """
    len(x) = m
    D.shape = m, n
    *mcrData*: list of dicts;
        defaultMCRDict = dict(initialS='auto', positiveS=True, zeroC=False,
                              constraintCKind='', constraintCValue=0.3)
    """

    N = len(mcrData)
    B = None
    found = []
    for i, d in enumerate(mcrData):
        ini = d['initialS']
        if ini == 'auto':
            col = unlike(B, D, found)
        elif ini == 'start':
            col = D[:, 0][:, None]
        elif ini == 'end':
            col = D[:, -1][:, None]
        elif ini == 'mean':
            col = D.mean(axis=1)[:, None]
        elif ini == 'reference':
            try:
                xref, yref = d['ref']
                interp = interp1d(
                    xref, yref, fill_value="extrapolate", assume_sorted=True)
                col = interp(x)[:, None]
            except Exception as err:
                print('Error in MCR-initial:', err)
                col = unlike(B, D, found)
        else:
            raise ValueError('Unknown initial rule for S{0}'.format(i+1))

        if B is None:
            B = col
        else:
            B = np.hstack((B, col))
            if B.shape[1] == N:
                break
    return B


def one_iteration(D, S, mcrData, weps=1e-20):
    """
    D.shape = m, n
    S.shape = m, N
    *mcrData*: list of dicts;
        defaultMCRDict = dict(initialS='auto', positiveS=True, zeroC=False,
                              constraintCKind='', constraintCValue=0.3)
    """
    N = S.shape[1]
    n = D.shape[1]
    STS = np.dot(S.T, S)
    try:
        ws, vs = spl.eigh(STS)
    except ValueError:
        print('singular S^TS')
        return np.zeros_like(S), np.zeros((n, N)), np.zeros((N, N))
    # print('STS w', ws/ws.sum())
    ws[ws < weps] = weps
    revSTS = np.dot(np.dot(vs, np.diag(1/ws)), vs.T)
    SrevSTS = np.dot(S, revSTS)
    C = np.dot(D.T, SrevSTS)

    # ==all these are bad:====================================================
    # C[C < 0.] = 0.
    # C[C > 1.] = 1.
    # C -= C.min()
    # C /= C.max()
    # # C /= C.sum(axis=1)[:, None]
    # ========================================================================

    C = np.abs(C)
    norm = C.sum(axis=1)[:, None]
    norm[norm == 0] = 1
    C /= norm

    changed = False
    for col, d in zip(range(N), mcrData):
        if d['zeroC']:
            C[:, col] -= C[:, col].min()
            changed = True

        val = d['constraintCValue']
        if d['constraintCKind'] == '>':
            C[C[:, col] < val, col] = val
            changed = True
        elif d['constraintCKind'] == '<':
            C[C[:, col] > val, col] = val
            changed = True

    if changed:
        norm = C.sum(axis=1)[:, None]
        norm[norm == 0] = 1
        C /= norm

    Cweight = C.sum(axis=0)
    Cind = np.argsort(Cweight)[::-1]
    Cweight = Cweight[Cind]
    C = C[:, Cind]  # [:, Cweight > 0]

    CTC = np.dot(C.T, C)
    try:
        wc, vc = spl.eigh(CTC)
    except ValueError:
        print('singular C^TC')
        return np.zeros_like(S), np.zeros_like(C), np.zeros((N, N))
    # print('CTC w', wc/wc.sum())
    wc[wc < weps] = weps
    revCTC = np.dot(np.dot(vc, np.diag(1/wc)), vc.T)
    CrevCTC = np.dot(C, revCTC)
    S = np.dot(D, CrevCTC)
    for col, d in zip(range(N), mcrData):
        if d['positiveS']:
            # ==all these are bad:============================================
            # S[S[:, col] < 0, col] = 0
            # if sum(S[:, col] < 0) > 0:
            #     S[:, col] -= S[:, col].min()
            # ================================================================
            S[:, col] = np.abs(S[:, col])
    return S, C, revCTC


def mcr_als(e, D, mcrData, retErrors=False, eps=1e-16, weps=1e-20,
            maxIteration=1000):
    S = initial(e, D, mcrData)
    m = len(e)
    normPrev = np.inf
    for niter in range(maxIteration):
        S, C, revCTC = one_iteration(D, S, mcrData, weps)
        epsD = D - np.dot(S, C.T)
        norm = spl.norm(epsD) / m  # can be directly compared with noise
        if abs(normPrev - norm) < eps:
            break
        normPrev = norm
        # if niter % 100 == 0:
        #     print(niter, 'eps', norm, normPrev)
    print('niter', niter, 'norm', norm)

    if retErrors:
        Cfit = []
        n = D.shape[1]
        for ispectrum in range(n):
            p0 = C[ispectrum, :]
            popt, pcov = curve_fit(
                lambda x, *coeffs: np.dot(S, coeffs), e, D[:, ispectrum], p0,
                sigma=1e-2, absolute_sigma=True, bounds=(0, 1))
            Cfit.append(popt)
            print(ispectrum, popt, np.sqrt(np.diag(pcov)))
        Cfit = np.array(Cfit)
        return S, C, revCTC, Cfit

    return S, C, revCTC

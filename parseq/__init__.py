# -*- coding: utf-8 -*-
u"""Package ParSeq is a python software library for Parallel execution of
Sequential data analysis.

The intention is to work on large data sets of ~103 spectra of ~103 data points
without delays in data treatment and plotting. The following desirable features
are missing in other analysis platforms and justify the creation of ParSeq:

1. Application of any parameter represented by a corresponding GUI element
   (e.g. a check box or a spin box) to one or several previously selected
   active data. Additionally, there should be a way of applying the last action
   to an a posteriori selected data subset.

2. Undo and redo for all treatment steps.

3. Entering into the analysis pipeline at any node, not only at the most
   upstream.

4. Creation of cross-data linear combinations (e.g. averaging, RMS or PCA) and
   their propagation downstream the pipeline together with the parental data.
   The possibility of termination of the parental data at any selected
   downstream node. Entering and termination of data flow at various nodes
   means that each node should have its own data manager window. This window
   can also function as a plot legend.

5. Parallel execution of data analysis on GPU.

6. Fast plotting software library capable of handling ~103 curves is needed.

ParSeq creates a data analysis pipeline consisting of nodes and transforms that
connect the nodes. The pipeline is fed with data (spectra), possibly entering
the pipeline at various nodes. The pipeline can be operated via scripts or GUI.
The mechanisms for creating nodes and transforms and connecting them together
are exemplified by the module `parseq\pipelines\dummy.py` (a simple pipeline)
and the script `examples\run_dummy.py` (the main script).
"""

# ======Naming Convention: note the difference from PEP8 for variables!========
# * classes MixedUpperCase
# * constants CAPITAL_UNDERSCORE_SEPARATED
# * varables lowerUpper *or* lower
# * functions and methods underscore_separated *or* lower
# =============================================================================

__module__ = "parseq"
__author__ = "Konstantin Klementiev (MAX IV Laboratory)"
__email__ = "first dot last at gmail dot com"
__versioninfo__ = (0, 0, 1)
__version__ = '.'.join(map(str, __versioninfo__))
__date__ = "17 Nov 2018"
__license__ = "MIT license"

#__all__ = ['core']

.. _history:

Version history
---------------

Current GitHub code (modified 30 Oct 2025):
    -

2025.10.0 (30 Oct 2025):
    - The functionality and look of ParSeq on macOS have been revised. Check
      boxes and radio buttons did not work. Tab widgets were of a small size
      and with a too dark background. Table headers and tree view headers were
      too small. All the above issues have been fixed.

    - The Save project dialog now sets its check boxes from the ini file.

    - Minor bug fixes and updates.

2025.8.0 (31 Aug 2025):
    - Add workaround for corrupt h5 files: stop using h5Model.insertFileAsync().

    - Minor bug fixes.

2025.3.1 (28 Mar 2025):
    - Bug fixes in doc builds.

    - Improve tie expressions in LCF.

2025.3.0 (13 Mar 2025):
    - Enable custom node icons.

    - Enable node arrays with an extra abscissa.

    - Add glitch detection.

    - Add metavariables to fits.

    - Enable several transformation widgets per node, with the idea to get a
      widget in the 'corrections' splitter.

    - Add optional interpolation when making data combinations.

    - Add Principal Component Analysis and Target Transformation to data
      combinations.

    - Minor new features and minor bug fixes.

2024.11.0 (23 Nov 2024):
    - Finalize general data corrections. Include doc pages with descriptions
      and animated examples. Add "delete spikes" data correction.

2024.5.0 (4 May 2024):
    - Add general data corrections.

    - Add EXAFS fit. It features two fit intervals (k and r), constraints,
      ties to other parameters (also of another data item) and error analysis.

    - Update the main help pages.

2023.5.0 (May 2023):
    - Add curve fitting facilities. Implemented 2 general fitting routines:
      linear combination fit and function fit.

1.0.0 (4 Apr 2023):
    - Functional ParSeq and a few pipelines.

... development releases ...

Nov 2018:
    Start GitHub repo `kklmn/ParSeq` after a year of development.

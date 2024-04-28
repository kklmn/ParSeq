# -*- coding: utf-8 -*-
from setuptools import setup
import os.path as osp
import codecs

__dir__ = osp.abspath(osp.dirname(__file__))


def read(pathnames):
    with codecs.open(osp.join(__dir__, *pathnames), 'r') as fp:
        return fp.read()


def get_long_description():
    inLines = read(('parseq', 'description.py')).splitlines()
    outLines = []
    # as (1st line of exclusion, the line _after_ exclusion)
    excludeBetweens = [('A screenshot of a', 'Main features')]
    excludeStates = [False] * len(excludeBetweens)
    for line in inLines:
        if line.startswith('#'):
            continue
        for ie, excludeBetween in enumerate(excludeBetweens):
            if line.startswith(excludeBetween[0]):
                excludeStates[ie] = True
            elif line.startswith(excludeBetween[1]):
                excludeStates[ie] = False
            if not excludeStates[ie]:
                outLines.append(line)
    return "\n".join(outLines[1:-1])  # exclude the tripple quotes


def get_version():
    inLines = read(('parseq', 'version.py')).splitlines()
    for line in inLines:
        if line.startswith('__versioninfo__'):
            versioninfo = eval(line[line.find('=')+1:])
            version = '.'.join(map(str, versioninfo))
            return version
    else:
        raise RuntimeError("Unable to find version string.")


setup(
    name='parseq',
    version=get_version(),
    description='ParSeq is a python software library for Parallel execution of'
                ' Sequential data analysis.',
    long_description=get_long_description(),
    long_description_content_type='text/x-rst',
    author='Konstantin Klementiev',
    author_email='konstantin.klementiev@gmail.com',
    url='http://parseq.readthedocs.io',
    project_urls={'Source': 'https://github.com/kklmn/ParSeq'},
    platforms='OS Independent',
    license='MIT License',
    keywords='data-analysis pipeline framework gui synchrotron spectroscopy',
    # python_requires=,
    zip_safe=False,  # True: build zipped egg, False: unzipped
    packages=['parseq',
              'parseq.core',
              'parseq.fits',
              'parseq.gui', 'parseq.gui.fits',
              'parseq.help',
              'parseq.tests', 'parseq.third_party', 'parseq.utils'],
    # package_dir={'parseq': '.'},
    package_data={
        'parseq': ['CODERULES.txt'],
        'parseq.gui': ['_images/*.*'],
        'parseq.help': [
            '*.rst', '*.bat',
            '_images/*.*', '_static/*.*', '_templates/*.*',
            '_themes/*/*.*', '_themes/*/*/*.*', 'exts/*.*'],
        'parseq.tests': ['*.png', 'data/*.*'],
        'parseq.third_party': ['data/*.*'],
        },
    install_requires=['numpy>=1.8.0', 'scipy>=0.17.0', 'matplotlib>=2.0.0',
                      'sphinx>=1.6.2', 'sphinxcontrib-jquery', 'autopep8',
                      'h5py', 'silx>=1.1.0', 'hdf5plugin', 'psutil',
                      'docutils', 'distro', 'colorama'],
    classifiers=['Development Status :: 5 - Production/Stable',
                 'Intended Audience :: Science/Research',
                 'Natural Language :: English',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'License :: OSI Approved :: MIT License',
                 'Intended Audience :: Science/Research',
                 'Topic :: Scientific/Engineering',
                 'Topic :: Software Development',
                 'Topic :: Software Development :: User Interfaces']
    )

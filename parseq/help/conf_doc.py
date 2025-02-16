# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = u'ParSeq XAS Documentation'
copyright = u'2018 Konstantin Klementiev'
author = 'Konstantin Klementiev'

extensions = ['sphinx.ext.mathjax']
exclude_patterns = ['_build', '_sources']

# The master toctree document.
master_doc = 'content'

rst_prolog = """
.. role:: red
.. role:: bigger
"""

add_function_parentheses = True
add_module_names = False

html_theme = 'parseq'
html_theme_path = ["./_themes"]
html_static_path = ['_static']

html_favicon = "_images/parseq.ico"

html_domain_indices = False

# If false, no index is generated.
html_use_index = False

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = False

html_scaled_image_link = False

import sys
import os.path
import sphinx_rtd_theme

sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('doc'))

import btzen

extensions = [
    'sphinx.ext.autodoc', 'sphinx.ext.autosummary', 'sphinx.ext.doctest',
    'sphinx.ext.todo', 'sphinx.ext.viewcode'
]
project = 'btzen'
source_suffix = '.rst'
master_doc = 'index'

version = release = '0.0.9'
copyright = 'Artur Wroblewski'

epub_basename = 'bme280 - {}'.format(version)
epub_author = 'Artur Wroblewski'

todo_include_todos = True

html_theme = 'sphinx_rtd_theme'
html_static_path = ['static']
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# vim: sw=4:et:ai

# -*- coding: utf-8 -*-
from importlib.metadata import metadata

__all__ = ['__package_name__', '__version__', '__title__', '__author__', '__email__', '__license__', '__copyright__', '__url__', '__help_url__']


package_metadata = metadata('ofstatement-french')
__package_name__ = package_metadata["Name"]
__version__ = package_metadata["Version"]
__title__ = package_metadata["Summary"]
__author__ = package_metadata["Author"]
__email__ = package_metadata["Author-email"]
__license__ = package_metadata["License"]
__url__ = package_metadata["Project-URL"][len("Repository, "):]
__help_url__ = package_metadata["Home-page"]
# Can not be set via metadata
__copyright__ = 'Copyright 2020-2023 Gert-Jan Paulissen'


def version():
    print(__version__)


def main():
    for var in __all__:
        try:
            print("%s: %s" % (var, eval(var)))
        except NameError:
            pass


if __name__ == '__main__':
    main()

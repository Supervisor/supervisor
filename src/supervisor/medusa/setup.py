
__revision__ = '$Id: setup.py,v 1.9 2003/08/22 13:07:07 akuchling Exp $'

from distutils.core import setup

setup(
    name = 'medusa',
    version = "0.5.4",
    description = "A framework for implementing asynchronous servers.",
    author = "Sam Rushing",
    author_email = "rushing@nightmare.com",
    maintainer = "A.M. Kuchling",
    maintainer_email = "amk@amk.ca",
    url = "http://oedipus.sourceforge.net/medusa/",

    packages = ['medusa'],
    package_dir = {'medusa':'.'},
    )

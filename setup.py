import os
import re
import sys
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
versionfile = open(os.path.join(here, 'docflow', '_version.py')).read()

mo = re.search(r"^__version__\s*=\s*['\"]([^'\"]*)['\"]", versionfile, re.M)
if mo:
    version = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in docflow/_version.py.")

if sys.hexversion < 0x2070000:
    # 2.6 and below require ordereddict
    requires = ['ordereddict', 'six']
else:
    requires = ['six']


setup(
    name='docflow',
    version=version,
    description='Python Document Workflows',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Libraries",
    ],
    author='Kiran Jonnalagadda',
    author_email='jace@pobox.com',
    url='http://github.com/jace/pydocflow',
    keywords='workflow',
    packages=['docflow'],
    include_package_data=True,
    zip_safe=True,
    test_suite='tests',
    install_requires=requires,
)

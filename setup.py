import os
from setuptools import setup, find_packages
import docflow

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

requires = [
    ]

setup(name='docflow',
      version=docflow.__version__,
      description='Python Document Workflows',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.2",
        "License :: OSI Approved :: BSD License",
        "Development Status :: 3 - Alpha",
        ],
      author='Kiran Jonnalagadda',
      author_email='jace@pobox.com',
      url='http://github.com/jace/pydocflow',
      keywords='workflow',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=True,
      test_suite='tests',
      install_requires=requires,
      )

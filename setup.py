import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = unicode(open(os.path.join(here, 'README.rst')).read(), 'utf-8')
CHANGES = unicode(open(os.path.join(here, 'CHANGES.rst')).read(), 'utf-8')

requires = [
    'ordereddict',
    ]

setup(name='docflow',
      version='0.3',
      description='Python Document Workflows',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.3",
        "Programming Language :: Python :: 2.4",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
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
      packages=find_packages(),
      include_package_data=True,
      zip_safe=True,
      test_suite='tests',
      install_requires=requires,
      )

__author__ = 'tom'
from setuptools import setup, find_packages

setup(
    name='python-pathfinder-tools',
    version='0.1',
    description='Python code to do various helpful pathfinder RPG related things',
    classifiers=['Programming Language :: Python :: 3.7'],
    url='https://github.com/tomoinn/python-pathfinder-tools/',
    author='Tom Oinn',
    author_email='tomoinn@gmail.com',
    license='ASL2.0',
    packages=find_packages(),
    install_requires=['requests==2.20.1', 'logzero==1.5.0', 'pydotplus==2.0.2', 'rply==0.7.6', 'pillow==5.3.0',
                      'fpdf==1.7.2'],
    include_package_data=True,
    test_suite='nose.collector',
    tests_require=['nose'],
    dependency_links=[],
    zip_safe=False)

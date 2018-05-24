# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='compellent',
    version='0.1.0',
    description='Manage Compellent storage using the REST API',
    long_description=readme,
    author='Joseph Wegner',
    author_email='joe@jwegner.io',
    url='https://github.com/jwegner89/compellent',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    keywords='Dell Compellent REST storage snapshot Oracle database Linux',
)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

#!/usr/bin/env python

from setuptools import setup

setup(
    name='dockerenv',
    version='1.0',
    description='Utilities for developing, testing, building and deploying code using docker',
    author='Alexey Akimov',
    url='https://github.com/subdir/dockerenv',
    scripts=['run'],
    packages=['dockerenv'],
    package_data={'dockerenv': [
        'debian_cleanup_wrapper.sh',
        'hostuser_entrypoint.sh',
        'image_init.sh',
    ]},
)


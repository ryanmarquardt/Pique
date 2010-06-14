#!/usr/bin/env python

from distutils.core import setup
import os

setup(name='pique', version='0.01',
	author='Ryan Marquardt',
	author_email='ryan.marquardt@gmail.com',
	description='Pique Media Center',
	url='http://orbnauticus.github.org/pique',
	packages=['pique'],
	package_data={'pique': ['table-def.conf']},
	license='Simplified BSD License',
	scripts=['piqued'] + [os.path.join('tools',s) for s in os.listdir('tools')],
)

#!/usr/bin/env python

from distutils.core import setup
from itertools import chain
import os

def find(path='.'):
	return list(chain(*[find(x) if os.path.isdir(x) else (x,) for x in map(lambda x:os.path.join(path,x),os.listdir(path))]))

setup(name='pique', version='0.02.3',
	author='Ryan Marquardt',
	author_email='ryan.marquardt@gmail.com',
	description='Pique Media Center',
	url='http://orbnauticus.github.org/pique',
	packages=['pique'],
	package_data={'pique': ['default.conf']},
	license='Simplified BSD License',
	scripts=['piqued'] + find('tools'),
)

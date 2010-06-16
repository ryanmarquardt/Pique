#!/usr/bin/env python

from distutils.core import setup
import os

def find(path='.'):
	r = []
	for f in os.listdir(path):
		if os.path.isdir(f):
			r.extend(find(f))
		else:
			r.append(os.path.join(path, f))
	return r

setup(name='pique', version='0.01.1',
	author='Ryan Marquardt',
	author_email='ryan.marquardt@gmail.com',
	description='Pique Media Center',
	url='http://orbnauticus.github.org/pique',
	packages=['pique'],
	package_data={'pique': ['table-def.conf', 'default.conf']},
	license='Simplified BSD License',
	scripts=['piqued'] + find('tools'),
)

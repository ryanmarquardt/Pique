#!/usr/bin/env python

import sys

copyright = open('COPYING').readlines()
notice = '#\n' + ''.join(['# '+l for l in copyright])
for path in sys.argv[1:]:
	fil = open(path).read()
	firstline,therest = fil.split('\n',1)
	if firstline[:2] == '#!' and not therest.startswith(notice):
		fil = open(path, 'w')
		#fil = sys.stdout
		fil.write(firstline + '\n')
		fil.write(notice)
		fil.write(therest)

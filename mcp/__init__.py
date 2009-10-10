#!/usr/bin/python

try:
	import pygtk
	pygtk.require('2.0')
except ImportError:
	pass
else:
	del pygtk

try:
	import pygst
	pygst.require('0.10')
except ImportError:
	pass
else:
	del pygst

__all__ = ['debug','lirc','server','types','client']



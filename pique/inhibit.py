#!/usr/bin/env python

import subprocess

class ScreensaverInhibitor(object):
	def __init__(self, cmd=['gnome-screensaver-command', '-i']):
		self.cmd = cmd
		
	def __enter__(self):
		self.proc = subprocess.Popen(self.cmd)
		
	def __exit__(self, err, t, tb):
		self.proc.kill()
		

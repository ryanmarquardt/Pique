#!/usr/bin/env python

import os
import re
import shutil
import subprocess
import sys

def debug(*args):
	print >>sys.stderr, ' '.join(map(str,args))

def abort(*args):
	print >>sys.stderr, 'Aborting:', ' '.join(map(str,args))

def backup(path, ext='bak'):
	newpath = '.'.join((path,ext))
	debug('Backing up', path, 'as', newpath)
	shutil.copy(path, newpath)
	
def restore(path, ext='bak'):
	bakpath = '.'.join((path,ext))
	debug('Restoring', path, 'from', bakpath)
	os.rename(bakpath, path)

def shrepr(a):
	return repr(a) if ' ' in a else a

def run(*args, **kwargs):
	stdout=kwargs.get('stdout',subprocess.PIPE)
	debug(*map(shrepr,args))
	return subprocess.Popen(args, stdout=stdout).communicate()[0]

if __name__=='__main__':
	FILES = ('debian/changelog', 'setup.py')
	if '--undo' in sys.argv[1:]:
		for f in FILES:
			restore(f)
		exit(0)
	else:
		for f in FILES:
			backup(f)
	
	lastversioncommit,_,lastversionnumber = [l for l in subprocess.Popen(['git', 'log', '--pretty=oneline'], stdout=subprocess.PIPE).communicate()[0].split('\n') if 'Version' in l][0].split(' ', 2)
	
	debug('Last version commit:', lastversioncommit)
	
	if len(sys.argv) > 1:
		newversionnumber = sys.argv[1]
	else:
		v = lastversionnumber.split('.')
		v[-1] = str(int(v[-1]) + 1)
		newversionnumber = '.'.join(v)
	
	debug('Bumping from version', lastversionnumber, 'to', newversionnumber)
	commitinfo = list(line[4:] for line in run('git', 'log', '%s..HEAD' % lastversioncommit).split('\n') if line.startswith('    '))
	if not commitinfo:
		abort('No commits since last version bump')
	
	run('dch', '--newversion', newversionnumber, commitinfo[0])
	for line in commitinfo[1:]:
		run('dch', '--append', line)
	
	setuppy = open('setup.py').read()
	setuppy = setuppy.replace(lastversionnumber, newversionnumber)
	open('setup.py', 'w').write(setuppy)
	
	run('dch', '-r', stdout=None)
	gitcommit = ['git', 'commit'] 
	gitcommit.extend(['-m', 'Version %s' % newversionnumber])
	gitcommit.append('-e')
	gitcommit.append('-v')
	gitcommit.append('--')
	gitcommit.extend(list(FILES))
	#if raw_input('Commit? (Y/n) ') in ('Y','y'):
	run(*gitcommit, stdout=None)

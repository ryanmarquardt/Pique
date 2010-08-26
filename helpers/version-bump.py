#!/usr/bin/env python

import os
from subprocess import *
import sys

dryrun = len(sys.argv) != 2

OLD_VERSION = Popen(['python', 'setup.py', '--version'], stdout=PIPE).communicate()[0].strip()

version,major,minor = map(int,OLD_VERSION.split('.'))
if sys.argv[1] == 'version':
    version += 1
elif sys.argv[1] == 'major':
    major += 1
elif sys.argv[1] == 'minor':
    minor += 1
NEW_VERSION = "%d.%02d.%d" % (version,major,minor)
print OLD_VERSION, '->', NEW_VERSION
sed = ['sed', 's/%s/%s/' % (OLD_VERSION, NEW_VERSION)]
print sed
if dryrun:
    Popen(sed + ['setup.py']).communicate()
else:
    Popen(['cp', 'setup.py', 'setup.py.old']).communicate()
    setup = Popen(sed + ['setup.py.old'], stdout=PIPE).communicate()[0]
    print setup
    open('setup.py','w').write(setup)
    distro = os.environ.get('DISTRO', Popen(['lsb_release', '-cs'], stdout=PIPE).communicate()[0])
    Popen(['dch', '-v', NEW_VERSION, '--distribution', distro]).communicate()

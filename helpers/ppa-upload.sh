#!/bin/sh
helpers/build.sh deb source-diff
dput ppa:ryan-marquardt/ppa ../pique_0.01_source.changes

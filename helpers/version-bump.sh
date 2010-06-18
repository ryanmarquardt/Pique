#!/bin/sh

OLD_VERSION=$1
NEW_VERSION=$2

cp setup.py setup.py.old
sed "s/$OLD_VERSION/$NEW_VERSION/" setup.py.old > setup.py

dch -v "$NEW_VERSION" --distribution maverick

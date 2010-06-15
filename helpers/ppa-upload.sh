python setup.py sdist
cd ..
tar -xz < Pique/dist/pique-0.01.tar.gz
cd pique-0.01
debuild -S -sa
dput ppa:ryan-marquardt/ppa ../pique_0.01_source.changes

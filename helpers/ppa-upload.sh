python setup.py sdist
cd ..
tar -xz < Pique/dist/pique-0.01.tar.gz
cd pique-0.01
debuild -S -sa

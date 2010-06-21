#!/bin/sh
export PY_FULLNAME=$(python setup.py --fullname)
export PACKAGE_VERSION=$(grep ^$(python setup.py --name) debian/changelog | head -n 1 | cut -d\( -f2 | cut -d\) -f1)
export PACKAGE_ARCH=$(dpkg-architecture -qDEB_BUILD_ARCH)
DEBUILD=$(which debuild)

verbose () { echo BUILD.SH "$@" >&2 ; "$@" ; }
indir () { ( cd "$1" ; shift ; "$@" ) ; }

pack () { python setup.py sdist ; }

unpack () {
	pack
	indir dist verbose tar -xf "${PY_FULLNAME}.tar.gz"
}

debuild () { indir "${PY_FULLNAME}" $DEBUILD "$@" ; }

debsource () {
	unpack
	indir "dist/${PY_FULLNAME}" debuild -S -sa
}

debsourcediff () {
	unpack
	indir "dist/${PY_FULLNAME}" debuild -S -sd
}

debbinary () {
	unpack
	indir "dist/${PY_FULLNAME}" debuild
}

deb () {
	case $1 in
		source)
			debsource
			echo pique_${PACKAGE_VERSION}_source.deb
			;;
		source-diff)
			debsourcediff
			echo pique_${PACKAGE_VERSION}_source.deb
			;;
		binary)
			debbinary
			echo pique_${PACKAGE_VERSION}_${PACKAGE_ARCH}.deb
			;;
		*)
			echo "Unknown architecture:" $1
			exit 2
			;;
	esac
}

case $1 in
	source)
		pack
		;;
	deb)
		deb $2
		;;
	run)
		pack
		unpack
		export PYTHONPATH="$PWD/dist/${PY_FULLNAME}"
		if [ -n "$3" ]; then
			shift 2
			indir "dist/${PY_FULLNAME}" "$@"
		else
			indir "dist/${PY_FULLNAME}" ./piqued
		fi
		;;
	*)
		echo "Unknown Command:" $1
		exit 1
		;;
esac

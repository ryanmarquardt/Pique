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

deb-source () {
	unpack
	indir "dist/${PY_FULLNAME}" debuild -S -sa
}

deb-source-diff () {
	unpack
	indir "dist/${PY_FULLNAME}" debuild -S -sd
}

deb-binary () {
	unpack
	indir "dist/${PY_FULLNAME}" debuild
}

deb () {
	case $1 in
		source)
			deb-source
			echo pique_${PACKAGE_VERSION}_source.deb
			;;
		source-diff)
			deb-source-diff
			echo pique_${PACKAGE_VERSION}_source.deb
			;;
		binary)
			deb-binary
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
	*)
		echo "Unknown Command:" $1
		exit 1
		;;
esac

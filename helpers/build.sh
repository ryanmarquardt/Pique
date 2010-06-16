export PY_FULLNAME=$(python setup.py --fullname)
export PACKAGE_VERSION=$(grep ^$(python setup.py --name) debian/changelog | head -n 1 | cut -d\( -f2 | cut -d\) -f1)
export PACKAGE_ARCH=$(dpkg-architecture -qDEB_BUILD_ARCH)

verbose () {
	echo BUILD.SH "$@" >&2
	"$@"
}

pack () {
	python setup.py sdist
}

unpack () {
	pack
	verbose tar -xf "dist/${PY_FULLNAME}.tar.gz"
	echo "${PY_FULLNAME}"
}

deb-source () {
	unpack
	( cd "${PY_FULLNAME}"; debuild -S -sa )
}

deb-source-diff () {
	unpack
	( cd "${PY_FULLNAME}"; debuild -S -sd )
}

deb-binary () {
	unpack
	( cd "${PY_FULLNAME}"; debuild )
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

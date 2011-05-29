#!/bin/sh
PYTHON=$(which python)
DEBUILD=$(which debuild)
SUBSHELL=${SHELL:-/bin/bash}
RM=$(which rm)
TAR=$(which tar)
DPUT=$(which dput)
DIR=$(dirname $(dirname $0))
cd $DIR

export PY_FULLNAME=$($PYTHON setup.py --fullname)
export PACKAGE_NAME=$($PYTHON setup.py --name)
export PACKAGE_VERSION=$($PYTHON setup.py --version)
export PACKAGE_FULLNAME=${PACKAGE_NAME}_${PACKAGE_VERSION}
export PACKAGE_ARCH=$(dpkg-architecture -qDEB_BUILD_ARCH)

verbose () { echo BUILD.SH "$@" >&2 ; "$@" ; }
indir () { ( cd "$1" ; shift ; "$@" ) ; }

pack () { "$RM" MANIFEST; "$PYTHON" setup.py sdist ; }

unpack () {
	pack
	indir dist verbose "$TAR" -xf "${PY_FULLNAME}.tar.gz"
}

debuild () { unpack; indir "dist/${PY_FULLNAME}" "$DEBUILD" "$@" ; }

deb () {
	ARCH=source
	case $1 in
		source)
			debuild -S -sa
			;;
		source-diff|diff)
			debuild -S -sd
			;;
		binary)
			debuild
			ARCH=${PACKAGE_ARCH}
			;;
		*)
			echo "Unknown architecture:" $1
			echo "Try one of:" source source-diff binary
			exit 2
			;;
	esac
	export DEBFILE="$PWD/dist/${PACKAGE_FULLNAME}_${ARCH}.deb"
}

case $1 in
	source)
		pack
		;;
	deb)
		deb $2
		echo "$DEBFILE"
		;;
	local-install)
		deb binary
		sudo dpkg -i "$DEBFILE"
		;;
	run)
		pack
		unpack
		export PYTHONPATH="$PWD/dist/${PY_FULLNAME}"
		export HOME="$PWD"
		export PATH="$PWD/dist/${PY_FULLNAME}/tools:$PATH"
		export PATH="$PWD/dist/${PY_FULLNAME}:$PATH"
		if [ -n "$2" ]; then
			shift 1
			indir "dist/${PY_FULLNAME}" "$@"
		else
			echo "Starting subshell with proper environment..."
			indir "dist/${PY_FULLNAME}" "$COLORTERM" &
			echo "Starting server..."
			indir "dist/${PY_FULLNAME}" ./piqued
		fi
		;;
	ppa-upload|ppa)
		deb source-diff
		if [ -n "$2" ]; then
			PPA="$2"
		elif [ -z "$PPA" ] ; then
			read -p "Which ppa would you like to upload to?" PPA
		fi
		"$DPUT" "$PPA" "dist/${PACKAGE_FULLNAME}_source.changes"
		;;
	*)
		echo "Unknown Command:" $1
		echo "Try one of:" source deb local-install run ppa
		exit 1
		;;
esac

# -*- Mode: Makefile -*-

clean:
	find ./ -name '*.pyc' -exec rm {} \;
	find ./ -name '*~' -exec rm {} \;

dist_debian:
	dpkg-buildpackage -rfakeroot


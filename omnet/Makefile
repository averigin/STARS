all: checkmakefiles
	cd src && $(MAKE)

clean: checkmakefiles
	cd src && $(MAKE) clean

cleanall: checkmakefiles
	cd src && $(MAKE) MODE=release clean
	cd src && $(MAKE) MODE=debug clean
	rm -f src/Makefile

makefiles:
	cd src && opp_makemake -f --deep --make-so -o stars-opp -O out -lbz2 -L/usr/lib64 -I/usr/include
 
makeall:
	cd src && opp_makemake -f --deep --make-so -o stars-opp -O out -lbz2 -L/usr/lib64 -I/usr/include
 
checkmakefiles:
	@if [ ! -f src/Makefile ]; then \
	echo; \
	echo '======================================================================='; \
	echo 'src/Makefile does not exist. Please use "make makefiles" to genrate it!'; \
	echo '======================================================================='; \
	echo; \
	exit 1; \
	fi

doxy:
	doxygen doxy.cfg

tcptut:
	cd doc/src/tcp && $(MAKE)

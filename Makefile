#!make

PANDOC=/usr/local/bin/pandoc

pyhislip.pyx: pyhislip.py pyhislip_pyx.template
	cat pyhislip_pyx.template pyhislip.py > temp.pyx
	mv temp.pyx pyhislip.pyx

README.txt:README.md
	$(PANDOC) -f markdown -t plain -o README.txt README.md

#!/usr/bin/make -f

.PHONY: build install checkout develop nodevelop

install:
	./subbuilder install
	sudo apt-get autoremove --yes
	sudo apt-get purge --yes
	sudo apt-get clean --yes
	sudo find /var/lib/apt/lists/ /tmp/ -mindepth 1 -maxdepth 1 -print0 | sudo xargs -0 -r rm -rf

%:
	./subbuilder $@


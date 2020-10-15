##
## Makefile for Tail server software
##

## Config

# Destination dir
INSTALL_DIR ?= /opt/rtls

# Local install root
INSTALL_ROOT ?= /

# Remote install
REMOTE ?= root@schottky.qs.unipart.io



## Files to install

EXEC = rtlsd

PTHN = \
	anchor.py	\
	config.py	\
	coord.py	\
	dwarf.py	\
	event.py	\
	filter.py	\
	lateration.py	\
	logger.py	\
	main.py		\
	mqrpc.py	\
	server.py	\
	tag.py		\
	tail.py		\
	tdoa.py		\
	timer.py	\
	wpan.py		\


CONF  =	rtls.conf	\
	logging.conf	\
	debug.conf      \

SERV  =	rtls.service


## Rules

.PHONY: all install remote-install clean

all:
	@echo "all done!"


install:
	install -o root -g root -m 755 -d $(INSTALL_ROOT)$(INSTALL_DIR)
	install -o root -g root -m 755 -d $(INSTALL_ROOT)$(INSTALL_DIR)/etc
	install -o root -g root -m 755 -d $(INSTALL_ROOT)$(INSTALL_DIR)/bin
	install -o root -g root -m 644 $(EXEC) $(INSTALL_ROOT)/usr/sbin/
	install -o root -g root -m 644 $(CONF) $(INSTALL_ROOT)$(INSTALL_DIR)/etc/
	install -o root -g root -m 644 $(PTHN) $(INSTALL_ROOT)$(INSTALL_DIR)/bin/
	install -o root -g root -m 644 $(SERV) $(INSTALL_ROOT)/lib/systemd/system/

remote-install:
	scp $(EXEC) $(REMOTE):/usr/sbin/
	scp $(CONF) $(REMOTE):$(INSTALL_DIR)/etc
	scp $(PTHN) $(REMOTE):$(INSTALL_DIR)/bin
	scp $(SERV) $(REMOTE):/lib/systemd/system/


clean:
	rm -fr __pycache__
	rm -f *~

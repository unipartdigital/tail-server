##
## Makefile for Tail anchor software
##

## Rules

.PHONY: all install remote-install clean

all:
	@echo "All done!"


install:
	@echo "Nothing to do locally"

remote-install:
	anchor-exec 'systemctl stop anchor ; test -d /opt/anchor || mkdir /opt/anchor ; rm -fr /opt/anchor/__pycache__'
	anchor-copy *.py *.conf /opt/anchor/
	anchor-copy anchor.service /lib/systemd/system/
	anchor-exec 'systemctl daemon-reload ; systemctl start anchor'

remote-upgrade:
	anchor-exec 'apt -y install python3-paho-mqtt'


clean:
	rm -fr __pycache__
	rm -f *~


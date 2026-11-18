#!/bin/bash
# Test-only: runs at the end of an unattended install. Adds a self-test that executes on
# first boot, logs the test user straight into the desktop, and reports over the serial port.
T=$1 USER_NAME=$2
printf '[Autologin]\nUser=%s\nSession=amadeus\n' "$USER_NAME" >$T/etc/sddm.conf.d/zz-selftest.conf
install -m755 /run/amadeus-auto/selftest.sh $T/usr/local/bin/amadeus-selftest
install -m755 /run/amadeus-auto/ui-check.py $T/usr/local/bin/amadeus-ui-check
install -m755 /run/amadeus-auto/e2e.py $T/usr/local/bin/amadeus-e2e
sed -i "s/@USER@/$USER_NAME/" $T/usr/local/bin/amadeus-selftest
cat >$T/etc/systemd/system/amadeus-selftest.service <<U
[Unit]
Description=Amadeus OS first-boot self-test
DefaultDependencies=no
After=graphical.target sddm.service
Before=shutdown.target
Conflicts=shutdown.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/amadeus-selftest
[Install]
WantedBy=multi-user.target
U
ln -sf ../amadeus-selftest.service $T/etc/systemd/system/multi-user.target.wants/

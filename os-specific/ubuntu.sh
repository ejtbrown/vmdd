#!/bin/bash

# Install required packages
apt-get update
apt-get -y install qemu qemu-kvm libvirt-daemon libvirt-clients bridge-utils virt-manager tuned samba net-tools isc-dhcpd-server nmap

# Remove packages that shouldn't be present
for pkg in dnsmasq firefox; do
  if dpkg -l "${pkg}" &> /dev/null; then
    apt-get -y remove "${pkg}"
  fi
done

if which snap &> /dev/null; then
  if snap list | grep firefox &> /dev/null; then
    snap remove firefox
  fi
fi

export DHCPD_SERVER_UNIT="isc-dhcp-server"
#!/bin/bash
# install.sh - sets up vmdd on the host

DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";

if which lsb_release &> /dev/null; then
  if lsb_release -a | grep Ubuntu &> /dev/null; then
    OS_TYPE="ubuntu"
    PRIMARY_USER=$(id 1000 | grep -Po '(?<=uid=1000\().*?(?=\))')
  else
    echo "Unknown OS type"
    exit 1
  fi
elif [[ -f /etc/redhat-release ]]; then
  OS_TYPE="fedora"
  PRIMARY_USER=$(id 1000 | grep -Po '(?<=uid=1000\().*?(?=\))')
else
  echo "Unknown OS type"
  OS_TYPE="unknown"
fi

# Perform OS-specific installation steps
if [[ -f "${DIR}/os-specific/${OS_TYPE}.sh" ]]; then
  # shellcheck source=os-specific/ubuntu.sh
  if ! source "${DIR}/os-specific/${OS_TYPE}.sh"; then
    echo "OS-specific installation steps failed; exiting"
    exit 1
  fi
else
  echo "WARNING: no OS-specific installation steps found!"
fi

# Give KVM users access to necessary files
chgrp libvirt /var/lib/libvirt/images
chmod 0660 /var/lib/libvirt/images/*
chown libvirt-qemu:kvm /var/lib/libvirt/images/*

# Setup the ephemeral images mount
cp "${DIR}/var-lib-libvirt-image.ephemeral.mount" "/lib/systemd/system/"
systemctl daemon-reload
systemctl enable --now var-lib-libvirt-image.ephemeral.mount

# Setup /VMShare
mkdir /VMshare
chmod 0777 /VMshare/
chown "${PRIMARY_USER}":"${PRIMARY_USER}" /VMshare

# Enable, start, and configure tuned (if it exists)
if systemctl list-unit-files | grep -q tuned.service; then
  systemctl enable --now tuned.service
  tuned-adm profile virtual-host
else
  echo "tuned appears not to be present; skipping optimizations"
fi

# Setup the bridges
if which netplan &> /dev/null; then
  cp "${DIR}/02-vmdd.yaml" "/etc/netplan/02-vmdd.yaml"
  netplan apply
else
  echo "Automatic setup of bridges failed; perform manual setup"
fi

# Setup Samba
cp "${DIR}/smbd.conf" "/etc/samba/smbd.conf"
mkdir /etc/samba/perm.conf.d
mkdir /etc/samba/temp.conf.d

chgrp sambashare /etc/samba/temp.conf.d/
chgrp sambashare /etc/samba/perm.conf.d/
chmod 0775 /etc/samba/perm.conf.d/

cp "${DIR}/etc-samba-temp.conf.d.mount" "/lib/systemd/system/"
systemctl daemon-reload
systemctl enable --now etc-samba-temp.conf.d.mount

echo "Enter password for Samba user (used for hubshare)"
smbpasswd -a "${PRIMARY_USER}"
systemctl enable --now smbd

# Setup hubshare & default network dhcpd
cp "${DIR}/dhcpd.conf" "/etc/dhcp/dhcpd.conf"

if [[ -n "${DHCPD_SERVER_UNIT}" ]]; then
  systemctl enable --now "${DHCPD_SERVER_UNIT}"
else
  echo "Manual enablement of dhcpd is required"
fi

# Setup hubshare / (short|long)cycle system permissions for KVM users
cp "${DIR}/sudoers" "/etc/sudoers.d/vmdd"

# Setup hubshare and (short|long)cycle
PY_MOD_DIR=$(dirname "$(python3 -c 'import os ; print(os.__file__)')")
cp "${DIR}/hubsharelib.py" "${PY_MOD_DIR}/hubsharelib.py"
cp "${DIR}/hubshare.py" "/usr/bin/hubshare"
cp "${DIR}/shortcycle.sh" "/usr/bin/shortcycle"
ln -s "/usr/bin/shortcycle" "/usr/bin/longcycle"

# Remove unnecessary packages and disable unnecessary services
if [[ "${OS_TYPE}" == "ubuntu" ]]; then
  systemctl disable --now cups.service
  systemctl disable --now ModemManager.service
  systemctl disable --now openvpn
fi

#!/usr/bin/env python3
"""
hubsharelib.py - objects for manipulating br-hub Samba shares

Authors:
  Erick Brown (https://github.com/ejtbrown)

License & Warranty:
  Licensed under GPL v3 (https://www.gnu.org/licenses/gpl-3.0.en.html)
  This software is provided as-is: no warranty is offered, expressed, or
  implied
"""

import re
import os
import subprocess
import secrets
import sys
import threading
import libvirt
import xml.dom.minidom
import io

var_types = {
    'path': str,
    'read only': bool,
    'writable': bool,
    'browsable': bool,
    'printable': bool,
    'guest ok': bool
}


def do_ping(ip):
    proc = subprocess.Popen(
        ['/usr/bin/ping', '-c1', ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    try:
        proc.wait(0.35)
        return
    except subprocess.TimeoutExpired:
        proc.kill()
        return


def get_mac_map():
    # Query the hypervisor for all the VM's MAC addresses
    try:
        conn = libvirt.openReadOnly(None)
    except libvirt.libvirtError:
        print('ERROR: Failed to open connection to the hypervisor', file=sys.stderr)
        return {}

    mac_map = dict()

    for vm in conn.listAllDomains():
        doc = xml.dom.minidom.parse(io.StringIO(vm.XMLDesc(0)))
        for node in doc.getElementsByTagName('devices'):
            i_nodes = node.getElementsByTagName('interface')
            for i_node in i_nodes:
                for v_node in i_node.getElementsByTagName('mac'):
                    mac_map[v_node.getAttribute('address')] = vm.name()

    return mac_map


def vm_find():
    mac_map = get_mac_map()

    # Ping all possible hosts in the subnet; this is done not to see if they
    # respond, but instead simply to ensure that the arp table is populated
    threads = list()
    for host in range(50, 254):
        threads.append(
            threading.Thread(
                target=do_ping,
                args=['172.16.10.' + str(host)]
            )
        )
        threads[-1].start()

    for thread in threads:
        thread.join()

    # Correlate IPs to VMs via MAC
    found = dict()
    arp_raw = subprocess.check_output(['/usr/sbin/arp', '-a', '-i', 'br-hub'])
    arp = dict()
    for line in arp_raw.decode('utf-8').splitlines():
        r_ip = re.search(r'(?<=\()[\d.]+', line)
        if r_ip is not None:
            r_mac = re.search(r'(?<= at )[\da-fA-F:]+', line)
            if r_mac is not None:
                arp[r_ip.group(0)] = r_mac.group(0)

    for ip in arp:
        if arp[ip] not in mac_map.keys():
            found[ip] = {'name': '<<unknown:unknown-mac>>', 'mac': arp[ip]}
        else:
            found[ip] = {'name': mac_map[arp[ip]], 'mac': arp[ip]}

    return found


def smbd_poke(should_be_loaded=True):
    ret = subprocess.call(
        ['/usr/bin/systemctl', 'status', 'smbd'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if ret == 0:
        ret = subprocess.call(
            '/usr/bin/sudo -n /usr/bin/systemctl reload smbd',
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True
        )
        if ret != 0:
            print("WARNING: reload of smbd failed (exit code " + str(ret) + ")", file=sys.stderr)
    else:
        if should_be_loaded:
            ret = subprocess.call(
                '/usr/bin/sudo -n /usr/bin/systemctl start smbd',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            if ret != 0:
                print("WARNING: start of smbd failed (exit code " + str(ret) + ")", file=sys.stderr)


def name_to_ip(vm):
    """
    name_to_ip - uses hubfind to find the IP of the named VM

    :param vm:      Name of VM to find
    :type vm: str
    :return:        Returns the IP of the VM
    :rtype: str
    """

    if re.search(r'\d+\.\d+\.\d+\.\d+', str(vm)):
        return vm

    output = subprocess.check_output(
        ['/bin/hubfind', vm]
    ).decode('utf-8')

    if len(output) > 0:
        return output.split()[0]

    raise IOError("Unable to find IP from VM name " + str(vm))


def ip_to_name(ip):
    """
    ip_to_name - uses hubfind to find the VM name of the specified IP

    :param ip:      IP of the VM
    :type ip: str
    :return:        Returns the VM name
    :rtype: str
    """

    if not re.search(r'\d+\.\d+\.\d+\.\d+', str(ip)):
        return ip

    output = subprocess.check_output(
        ['/bin/hubfind', ip]
    ).decode('utf-8')

    if len(output) > 0:
        return output.split()[1]

    raise IOError("Unable to find VM name form IP " + str(ip))


def delete_conf(file_name):
    if os.path.isfile(file_name):
        file_size = os.path.getsize(file_name)
        for p in range(0, 2):
            with open(file_name, 'wb') as f:
                f.write(secrets.token_bytes(file_size))

        os.unlink(file_name)

        smbd_poke(should_be_loaded=False)


class ShareVar(object):
    def __init__(self, name, val=None):
        global var_types

        self.name = name
        self.val = None
        self.set(val)

    def set(self, val):
        global var_types

        if self.name in var_types.keys():
            if issubclass(type(val), var_types[self.name]):
                self.val = val
            elif issubclass(var_types[self.name], bool):
                if val.lower() == 'yes':
                    self.val = True
                else:
                    self.val = False
            else:
                self.val = var_types[self.name](val)
        else:
            self.val = str(val)

    def __repr__(self):
        global var_types

        r_val = '  ' + self.name + ' = '
        if self.name in var_types.keys():
            if issubclass(var_types[self.name], bool):
                if self.val:
                    r_val += 'yes'
                else:
                    r_val += 'no'
            else:
                r_val += str(self.val)
        else:
            r_val += str(self.val)

        return r_val


class ShareDef(object):
    def __init__(self, name, parse=None):
        self.name = name
        if parse is None:
            self.__params__ = [
                ShareVar('path', ""),
                ShareVar('read only', False),
                ShareVar('guest ok', False),
                ShareVar('browsable', True),
                ShareVar('printable', False)
            ]
        else:
            self.__params__ = list()
            for line in str(parse).splitlines():
                match = re.search(r'(?<=\[).*(?=])', line)
                if match is not None:
                    self.name = match.group(0)
                else:
                    kv = line.split('=')
                    if len(kv) > 1:
                        self.__params__.append(ShareVar(kv[0].strip(), kv[1].strip()))

    def __repr__(self):
        r_val = '[' + self.name + ']\n'
        for param in self.__params__:
            r_val += str(param) + '\n'

        return r_val + '\n'

    def __getitem__(self, item):
        if item == 'name':
            return self.name

        real_item = item.replace('_', ' ')
        for param in self.__params__:
            if param.name == real_item:
                return param.val

        raise KeyError('Bad key "' + real_item + '"')

    def __setitem__(self, item, val):

        real_item = item.replace('_', ' ')
        for param in self.__params__:
            if param.name == real_item:
                param.set(val)
                return

        self.__params__.append(ShareVar(real_item, val))


class HubConf(object):
    def __init__(self, vm, perm=False):
        vm_map = vm_find()

        file_path = '/etc/samba/'
        if perm:
            file_path += 'perm'
        else:
            file_path += 'temp'
        file_path += '.conf.d/'

        self.perm = perm
        self.mac = None
        if re.search(r'\d+\.\d+\.\d+\.\d+', vm):
            self.ip = vm
            self.vm = None
        else:
            self.vm = vm
            self.ip = None

            # Check in the vm_map to find the IP
            for ip in vm_map.keys():
                if vm_map[ip]['name'] == vm:
                    self.ip = ip
                    break

            if self.ip is None:
                # This probably means that the VM is offline
                check_name = '# VM: ' + vm
                for check_file in os.listdir(file_path):
                    with open(file_path + check_file, 'r') as cf:
                        if cf.read(len(check_name)) == check_name:
                            self.ip = re.search(r'\d+\.\d+\.\d+\.\d+(?=\.conf)', check_file).group(0)
                            break

                if self.ip is None:
                    raise ValueError("Invalid VM '" + vm + "'")

        self.file_name = file_path + str(self.ip) + '.conf'

        self.shares = list()

        if os.path.isfile(self.file_name):
            with open(self.file_name, 'r') as f:
                accumulate = ''
                for line in f.readlines():
                    match = re.search(r'(?<=# VM: ).*', line)
                    if match is not None:
                        self.vm = match.group(0)

                    match = re.search(r'(?<=# MAC: ).*', line)
                    if match is not None:
                        self.mac = match.group(0)

                    if len(line.strip()) == 0:
                        self.shares.append(ShareDef('', accumulate))
                        accumulate = ''
                        continue

                    if line[0] != '#':
                        accumulate += line + '\n'

                if len(accumulate) > 0:
                    self.shares.append(ShareDef('', accumulate))
        else:
            self.vm = ip_to_name(vm)

        if self.mac is None:
            if re.search(r'(?<==<<).*?(?=>>)', vm_map[self.ip]['mac']):
                raise RuntimeError("Failed to get MAC for VM" + vm)
            self.mac = vm_map[self.ip]['mac']

    def __contains__(self, name):
        for share in self.shares:
            if share.name == name:
                return True

        return False

    def __repr__(self):
        output = '# VM: ' + self.vm + '\n'
        output += '# MAC: ' + self.mac + '\n'
        for share in self.shares:
            output += str(share)

        return output

    def add_share(self, name, **kwargs):
        if name in self:
            raise ValueError("Share '" + name + "' already declared")

        new_share = ShareDef(name)
        for arg in kwargs.keys():
            new_share[arg] = kwargs[arg]

        self.shares.append(new_share)
        return new_share

    def del_share(self, name):
        for index in range(0, len(self.shares)):
            if self.shares[index].name == name:
                del self.shares[index]
                return

    def save(self):
        if len(self.shares) == 0:
            self.delete()
            return
        else:
            with open(self.file_name, 'w') as f:
                f.write(str(self))

        smbd_poke()

    def delete(self):
        delete_conf(self.file_name)

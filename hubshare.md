# hubshare
### Overview
`hubshare` is a tool intended to facilitate easy movement of files between VMs
and the host OS. KVM lacks a convenient way to expose parts of the host OS to
guest OSes.

### Architecture
The host OS is configured with a bridge called `br-hub`, where it has an IP
of 172.16.10.1 and hosts DHCP for any clients connected to the bridge. This
allows for VMs to access hubshare services simply by adding a network device
attached to `br-hub`. It should be noted that this network does not provide
any routing - it will not provide internet access to the VMs, so this network
is intended to be used in conjunction with the default NAT network.

`hubshare` uses ARP to associate the MAC addresses of the devices on `br-hub`
with their IP addresses, and queries libvirt to find the VMs which have those
MAC addresses. In this way, it is able to know the relationship between VM
name, `br-hub` MAC address, and 172.16.10.0/24 IP addresses.

Samba is configured to dynamically include configuration files whose names
include the IP address of the client (specifically in the directories
`/etc/samba/temp.conf.d` and `/etc/samba/perm.conf.d`). When `hubshare`
sets up configurations for specific VMs, it uses this mechanism to create
configurations that are unique to each VM. This allows for granular control
of which VMs are able to access which parts of the host OS filesystem.

`hubshare` Samba configurations come in two flavors: permanent and temporary.
Permanent configurations remain in place until they are explicitly removed.
Temporary configurations are stored in a tmpfs, and do not persist through
host reboots (although they can be explicitly removed, just like permanent
configurations).

The default Samba configuration includes a read-only, guest-ok share of
`/VMshare`, which is intended to be a place to drop files for consumption
by VMs, such as software installation packages.

### Usage
```
usage: hubshare [-h] [-r] [-g] [-p] [-t TIMEOUT] [-a ALLOW] [-e] action [vm] [path] [name]

positional arguments:
  action                add|remove|list|find|wait|delete|clean
  vm                    VM name or IP
  path                  Host path to share
  name                  Name of the share

options:
  -h, --help            show this help message and exit
  -r, --readonly        Set share to read-only
  -g, --guest           Allow guest access
  -p, --permanent       Make the share permanent
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout (in seconds) for wait action
  -a ALLOW, --allow ALLOW
                        Hosts or CIDR ranges permitted to access the share
  -e, --private         Limit access down to only the target VM
```

*Note on --private*
The -e/--private flag sets the `hosts allow` parameter to the target VM's IP on the hubshare
network. Since hubshares are already per-host configurations, it _shouldn't_ be possible for
other hosts to access them, because Samba _shouldn't_ acknowledge that they exist to other
hosts. The purpose of this flag is to add another layer of security

Actions:
- add: adds a new share to the specified VM
- remove: removes a share from the specified VM
- delete: removes all shares from the specified VM
- clean: removes config files for VMs that no longer exist
- list: lists all shares currently configured via hubshare
- find: finds and displays all VMs on the `br-hub` bridge
- wait: waits for the specified VM to appear on the `br-hub` bridge

#### Examples:
_Add a new share for the VM 'untrusted-0'_
```bash
$ hubshare add untrusted-0 /home/user/tmp user-temp
```

_Remove the share_
```bash
$ hubshare remove untrusted-0 /home/user/tmp user-temp
```

_Remove all shares from a VM_
```bash
$ hubshare delete untrusted-0
```

_Get a list of current shares_
```bash
$ hubshare list
#### Permanent Shares ####
VM          | IP            | Name  | Path      | Read Only | Guest OK
----------------------------------------------------------------------
personal-0  | 172.16.10.59  | logs  | /var/log  | False     | False   

#### Temporary Shares ####
VM          | IP            | Name  | Path      | Read Only | Guest OK
----------------------------------------------------------------------
personal-0  | 172.16.10.59  | tmp   | /tmp      | False     | False   
```

_Find the VMs on the `br-hub` bridge_
```bash
$ hubshare find
IP              | MAC               | VM
---------------------------------------------
172.16.10.59    | 52:54:00:f3:88:e7 | personal-0
```
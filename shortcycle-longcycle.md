# shortcycle & longcycle
### Overview
`shortcycle` and `longcycle` are convenient lifecycle management tools for
clones of template VMs. As their name implies, `shortcycle` is intended to
address short-term use cases, and `longcycle` is intended to address longer
term use cases.

`shortcycle` will clone and start the specified template VM, and wait for it
to shut down. Once the shutdown happens, it will delete the VM and clean up the
data, such as the virtual drives, NVRAM, and logs. This is ideal for cases 
where a clone is needed for some immediate purpose, and there is no desire to 
retain any accumulated data on the VM. Clones produced by `shortcycle` will be
named after the template VM, along with a number. For example, the first clone
of a template called `untrusted-template` would be `untrusted-tempclone-0`.

`longcycle` will clone the specified template VM, and return once it has the VM
started. The user is responsible for the eventual destruction and deletion of
the VM. Clones produced by `longcycle` will be named after the template VM,
along with a number. For example, the first clone of a template called 
`work-template` would be `work-0`.

Both `shortcycle` and `longcycle` make thin clones of the template VMs volumes.
In addition to being much faster, this also saves drive space. The files for 
the clone VMs volumes will contain only the blocks that are _changed_ by the
clone; all the remaining blocks remain in the template VMs volume files.

### Usage
```
usage: shortcycle [-h] [-n] [-e] [-s] template-vm
usage: longcycle [-h] [-n] [-e] [-s] template-vm

positional arguments:
  template-vm           Name of the template VM to clone

options:
  -h                    show this help message and exit
  -n                    No internet (removes default NIC)
  -e                    Ephemeral volume in tmpfs
  -s name=/path         Add hubshare to clone
```

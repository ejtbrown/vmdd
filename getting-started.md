# Getting Started
The purpose of this document is to describe the steps necessary to configure
a computer to live the `vmdd` lifestyle. This document assumes that the
baremetal OS is Ubuntu 22.04. It should be possible to do `vmdd` on any modern
Linux distro, but the particular steps will of course be different.

# System Requirements
- Hardware virtualization support
- x64 architecture
- Sufficient memory for as many VMs as will need to run concurrently. In
  practical terms, the more memory the better
- Sufficient storage for as many VMs as will be present. In practical terms,
  more is always better, but even a few hundred GB could be made to work.

Those are the hard requirements. That said, the `vmdd` experiecnce is heavily
dependent on compute horsepower - the more the better. More CPU cores, faster
clock speeds, more RAM, faster RAM, faster storage, faster bus speeds - all
these things will have a profound impact on the overall experience.

# A Word About Threat Modeling
At its core, the vmdd lifestyle is about leveraging virtualization technology
to improve security. There are going to be a number of decisions to make in the
process of setting up your computer for vmdd. Making the right decisions 
depends on understanding yourself and your adversary. 

Are you a welder who just wants to avoid beign a notch on the belt of a 
randsomware gang? A systems administrator with deep access into critical 
infrastructure that competitors would hack to get access to? A human rights
activist operating covertly in a hostile nation? A drug dealer (yes, security
techonologies are going to be employed by the just as well as the wicked) who
needs to keep records and communications secure from law enforcement?

And what about your adversaries? Are they profit-motivated hackers who spread
a wide net, not caring about individual targets? Nation-state actors who are
trying to leverage your access into a larger organization? Law enforcement
agents trying to collect evidence against you or an acquaintance? Can they
break down your door and seize your equipment or are they limited to attacking
over the Internet? Can they seize _you_ and compel (by law, torture, or 
threat) you to breach your own security?

Taking a moment to consider these things will help guide the further decisions
to be made in during the setup of your vmdd system.

# A Word About Passwords
Choosing good passwords is a critical piece of the security puzzle. A good
password is one that is easy to remember, easy to type, hard to guess, and
hard to brute-force. Thre are numerous strategies for achieving this. Some
popular methods worth considering:

- Diceware: (https://en.wikipedia.org/wiki/Diceware) is an excellent system
  for chosing random English words. Five or six diceware words provides a
  password that is quite strong indeed, and is also easy to type and remember.
  There are also good websites available for automatically generating diceware
  passwords without the hassle of all the physical dice rolling and page
  turning
- Passphrase: the chorous to a beloved song, a favorite scripture verse, or
  the opening sentence of your favorite book can all make for good passwords.
  One word of caution however in choosing this strategy: it undermines the
  "hard to guess" requirement by making it so that someone who knows you well
  could make an educated guess

Strategies to avoid:
- Random strings: unless you happen to be freakishly good at memorizing long
  strings of random letters and numbers, this is a bad strategy because it
  encourages the password to be written down or saved somewhere
- Birthdays / anniversaries: dates are among the most loosely controled bits
  of personally identifying information. Potential adversaries are virtually
  certain to have access to this information, making it easy to guess
- Short passwords: modern computing affords massive resources to hackers. A
  short password is very close to having no password at all

# Download the Baremetal OS
This guide assumes Ubuntu 22.04 Desktop. It can be downloaded from
https://ubuntu.com/download/desktop

The ISO can be burned to a DVD (if your system has a DVD drive), or written to
a USB drive. See https://ubuntu.com/tutorials/create-a-usb-stick-on-ubuntu#1-overview 
and https://ubuntu.com/tutorials/create-a-usb-stick-on-windows#1-overview for
details on how to do the USB write.

# Install the Baremetal OS
This guide will not address how to make your system boot the DVD or USB, as
there are inumerable possible answers.

During the installation, you will be prompted for language, keyboard layout,
timezone, etc. Choose whichever seems most appropriate to your circumstances.

Among the options that you will be presented with is the option to encrypt the
disk. The decision to do so or not is entirely up to you, but since one of the
primary focuses of `vmdd` is security, the use of encrypted volumes can be
considered offically recommended by the project.

When prompted for what to install, choose "Minimal Desktop." Even the minimal
desktop is more than we actually want for vmdd, so the installation will be
removing and disabling things even from this!

Once the OS installation is complete, open a terminal window and install git:
`sudo apt-get update && apt-get -y install git` .

Run the vmdd install script: `sudo vmdd/install.sh` . This should perform the
setup steps necessary to finish preparing your system for livin' the vmdd
lifestyle.

Open Virtual Machine Manager (Activities -> type `Virtual Machine Manager`).

At this point, we have a system which is ready to beging building template VMs.
Using the Ubuntu 22.04 ISO that you already downloaded, build a simple Ubuntu
22.04 VM. Don't worry too much about the details, because we're not going to
be keeping it for very long. It has one purpose in life: to download the ISOs
for whatever operating systems we want to run on our VMs going forward.

Choose a list of operating systems that you want to run. Using the temporary
Ubuntu VM, download ISOs for whatever OSes you want to run. Be sure to also
download an ISO for the server version of your favorite Linux distro - you'll
be using it to run the local fileserver on the `br-files` virutal network.
While you're waiting for them to download, add a new network interface to the
temporary VM. In the Virtual Machine Manager window menu, View -> Details ->
Add Hardware -> Network; select 'Bridge' from the 'Source' pulldown, then 
enter `br-hub` in the device name. This will add a virtual NIC on the hubshare
bridge network. Next, open a terminal on the host (baremetal OS) and use the
hubshare command to share your download directory with the temporary VM
(assumed to be called `tempvm` for this example) - 
`hubshare add tempvm "${HOME}/Downloads" dl`. If hubshare claims that it can't
find the VM, check the name of the VM, and check to make sure that the
`br-hub` network was actually added to the VM. Inside the temp VM, open the
hubshare shared directory: Files app -> Other Locations -> Connect to server:
`smb://172.16.10.1`. Enter the username and password that was set for Samba
during installation. Copy the downloaded ISOs into this directory.

Now that you have the ISOs on the baremetal OS, you can delete the temp VM
and get started on building your templates. The first one to make is the file
server. Using Virtual Machine Manager, create a new VM using the ISO for your
favorite Linux server distro. Allocate however much space you feel is 
appropriate for the operating system in one volume, and ceate another volume to
store your files, allocating however much space you need. Using LVM on this
file storage volume is recommended, so that you can add more space later if
with minimal difficulty. Once this VM is built and the extra storage added,
add another network interface to the VM, and configure it for the `br-files`
bridge. In the VM, configure this VM to run on 172.16.23.10. You can choose
different IP address ranges, but be sure to update `/etc/netplan` on the
baremetal OS if you do. Configure NFS and Samba to listen on 172.16.23.10, and
accept connections only from 172.16.23.0/24. Configure a DHCP service on this
fileserver to manage the 172.16.23.0/24 subnet. The dnsmasq service can be
made to do this with this config:
```bash
$ cat > /etc/dnsmasq.conf <<EOF
port=0
interface=enp2s0
listen-address=172.16.23.10
no-hosts
domain=localdomain
dhcp-range=172.16.23.128,172.16.23.250,24h
EOF
```
Make sure that the DHCP service is running and enabled: 
`systemctl enable --now dnsmasq` .
Out of the all the VMs that the baremetal host will run, this is the only one
that doesn't conform to the disposable template model.

Once your fileserver VM is finished, it's time to begin on the template VMs.
The first template VM that we'll make is the one for personal files and 
authetnicated sites (i.e. stuff you log into). Create a new VM, and call it
`personal-template`. Add two new network interfaces, one on `br-files` and
the other on `br-hub` so that it can talk to the fileserver and particpate in
hubshare. Setup this VM with all of the software that you think that you're
going to need. Sign into all the services that you routinely use. In short,
do all of the stuff that you'd normally do when setting up a new computer for
yourself. But *DON'T* actually use the system to accomplish anything - the
only thing that we're doing in this step is to make ourselves at home in the 
VM. This should include setting up NFS/CIFS (depending on the OS) to the file
server VM so that your files are conveniently available. Once everything is
setup to your liking, shut down the VM. From this point on, the only time that
you'll power up this VM is to change the configuration (e.g. install some new
piece of software) or to perform system updates. Now that the template VM is
done and shut down, we can make a clone of it. From a terminal window on the
baremetal OS, run `longcycle personal-template`. This will create a thin clone
of the personal-template VM called `personal-0`. This new VM is the one that
we will use for day-to-day usage.

The next template that we'll create is the untrusted template. Everyday usage
of the Internet involves some amount of browsing through various websites that
require no authentication and are maintained by persons unknown to you. The
purpose of the untrusted VM is to keep browsing of these sites separate from
sensitive things, like your email, banking, etc. The steps for creating the
VM are essentially the same - name the VM something like `untrusted-template`,
install the OS and whatever software you think you'll need. Once everything is
setup to your liking, shut down the VM. As with the other templates, the only
time that you'll ever start it up again is for updates and configuration 
changes. In a terminal window on the baremetal OS, run 
`longcycle untrusted-template`. This will create a thin clone called 
untrusted-0. This VM will be the one that you'll use for day-to-day browsing
of untrusted websites.

When it's time to do a system update on one of the VMs, simply delete the
clone (e.g. personal-0), update the template, then make a new clone with the
`longcycle` command.
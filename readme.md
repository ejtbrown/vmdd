# vmdd - Virtual Machine Disposablility Desktop
### Overview
Cybersecurity is a topic that everyone is well advised to take seriously.
Securing ordinary desktop systems presents unique, and difficult challenges,
because the weakest link in any digital security system is inevitably the 
user. Sooner or later (s)he is going to make a mistake that will compromise
the integrity of the system.

The purpose of this project is to (partly) overcome this problem by bringing 
disposability to desktop computing. The concept of disposability is that every
so often, you throw your computer in the trash and start fresh with a new one.
This is obviously impractical for a number of reasons, but modern 
virtualization tools can get us pretty close to the same result without the
expense of buying a new computer every week, and without the hassle of setting
up a new computer every time.

The normal use model for a desktop computer is that the user runs the operating
system of their choice on the computer, installs whatever software they use in
that operating system, and store their files on the hard drive. In the `vmdd`
model, the computer exists _only_ to run VMs, and the user's stuff is decamped
into those VMs. Everything is arranged in such a way that those VMs (and indeed
the computer itself) can be disposed of quickly and easily, without losing
important data or having to start from scratch with a new setup.

This project draws on inspiration from Qubes (see https://www.qubes-os.org/
for details), but shares essentially no common elements (aside from both 
making extensive use of Linux). Qubes should be considered to be more secure
than this project. Which raises the question, why bother with this? The
answer is that while Qubes is unbeatable in security, the hardware 
compatibility list makes it difficult to overcome the primary limitation of
the approach (i.e. by buying a newer, more powerful computer). This project
runs on top of existing, modern Linux distributions, making available the very
latest in hardware support.

### Features
- All components are either part of this project or FOSS
- Support thin cloning of VMs (speeding VM cloning and saving space)
- Provides tooling for easy sharing of files between VMs and host via Samba

### Operating System Support
`vmdd` uses KVM and QEMU, so Linux is a prerequisite for the host operating 
system. It can probably be made to work on essentially any modern Linux 
distribution, but is known for sure to work on Ubuntu 22.04.

Any guest operating system supported by the processor architecture of the host
should work. That being said, operating systems with KVM guest tools and 
drivers are probably the best choice. 

#### Linux Guests
Most modern Linux distros come with KVM guest tools, making them an easy and
obvious choice. The one notable nuisance limitation is that display scaling
(in Gnome, at least) does not work well. To work around this, 
[scale-enforce](https://github.com/ejtbrown/scale-enforce) can be used.

#### Windows Guests
Windows should install without issues on a KVM VM. It should be noted however
that the desktop responsiveness is absolutely horrible until the KVM guest
tools and drivers are installed. Once they are, these problems should go away.

#### MacOS Guests
While running MacOS guests is technologically feasible, it is a violation of 
Apple's license terms for that product (also note that this document in no way 
should be construed to contain legal advice; if you have questions about the 
legality of running MacOS as a guest on `vmdd`, speak to an appropriately 
licensed and certified attorney in your jurisdiction).

### The Right Way To Use `vmdd`
The first cardinal rule of `vmdd` is that you never use the host operating 
system (i.e. what boots when the computer turns on) for routine day-to-day 
tasks - the _only_ thing you should be doing in the host OS is tasks related to
management of VMs and OS updates. Don't use the host OS for web browsing. Don't
use it for word processing. Don't use it for programming, or playing media, or 
anything of the sort. Instead, use VMs for those tasks.

Create a template VM for each of the different security contexts in which
you operate. What is a security context? The precise meaning varies from
one person to the next, but the essential idea is limiting the exposure when
you get hacked: when attackers take control of a VM, they can go no further
than that one VM. The simplest security context segregation is "stuff that
requires passwords" versus "stuff that doesn't." For that, we would have
two template VMs. We'll call them `personal-template` and 
`untrusted-template`. The names don't matter, except for them ending with
`-template` (which is a requirement for some tooling in this project). The
operating system running on these VMs is entirely up to you - whatever you
like to use is fine. Each template VM is set up with all the software that you
think that you'll need in each of those security contexts. In the case of the
`personal-template` VM, you'd also log into whatever software and websites you
think that you'll routinely use. The idea there is to set up the VM the way 
that you would a new computer, but to avoid actually _using_ it for anything
yet. Once the template VM is all set, ready to use, shut it down. From this 
point forward, the _only_ time that you run a template VM is to update it,
alter configuration, or install/remove software.

Having pristine templates is great, but how are you supposed to actually get
anything done? The answer is cloning! Use `shortcycle` or `longcycle` (see
[shortcycle-longcycle.md](shortcycle-longcycle.md)) to create clones of your 
templates, and use the clones. That way, when you're hacked, the clone can be
deleted and made fresh from the still-pristine template. When it's time to do 
an OS update, or install new software, destroy the clone and update the 
template, then make a new clone. In this way, the template is always ready to
go, like a computer that you just finished getting setup for yourself.

One of the benefits of this approach is that the setup time for the host
operating system is fairly brief, which makes it feasible to wipe the system
and reinstall fresh. All you have to do is copy the VMs to removable (or
remote) storage, install the new host OS, setup `vmdd`, then copy them back.

### What About My Files?
Having a fresh template VM is all well and good, but an obvious limitation to
this approach is that normal usage of a computer results in accumulating files
that the user wants to keep. The solution to this in the context of the vmdd
model is to run a file server VM, and have it host NFS and/or CIFS on a virtual
network. Only VMs which should have access to these files should be added to 
that virtual network. To this end, the virtual network `br-files` is created by
the installation script in this repo.

The other challenge to overcome with files in the vmdd model is moving files
around from one VM to another. To address this use case, this repo contains the
`hubshare` tool, and the installation script sets up another virtual network
called `br-hub` for its use. `hubshare` allows for specific locations within
the host filesystem to be selectively shared with specific VMs. In this way,
files can be made available across various VMs with a great degree of granular
control in access. See [hubshare.mb](hubshare.md) for more details.

### Contributions
Contributions are welcome. Please feel free to fork and submit pull requests!

### License & Warranty
Licensed under GPL v3 (https://www.gnu.org/licenses/gpl-3.0.en.html)
This software is provided as-is: no warranty is offered, expressed, or implied
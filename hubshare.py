#!/usr/bin/env python3
"""
hubshare.py - CLI for management of br-hub shares

Authors:
  Erick Brown (https://github.com/ejtbrown)

License & Warranty:
  Licensed under GPL v3 (https://www.gnu.org/licenses/gpl-3.0.en.html)
  This software is provided as-is: no warranty is offered, expressed, or
  implied
"""

import hubsharelib
import argparse
import sys
import os
import re
import time
import secrets

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--readonly', action='store_true', help='Set share to read-only')
    parser.add_argument('-g', '--guest', action='store_true', help='Allow guest access')
    parser.add_argument('-p', '--permanent', action='store_true', help='Make the share permanent')
    parser.add_argument('-t', '--timeout', help='Timeout (in seconds) for wait action', default=60)
    parser.add_argument('action', help='add|remove|list|find|wait|delete|clean')
    parser.add_argument('vm', nargs='?', default=None, help='VM name or IP')
    parser.add_argument('path', nargs='?', default=None, help='Host path to share')
    parser.add_argument('name', nargs='?', default=None, help='Name of the share')
    args = parser.parse_args()

    # Argument validation
    if args.action not in ['add', 'remove', 'list', 'find', 'wait', 'delete', 'clean']:
        print("Action must be either add, remove or list", file=sys.stderr)
        sys.exit(1)

    if args.action in ['add', 'remove']:
        if not os.path.isdir(args.path):
            print("Path " + args.path + " does not exist")
            sys.exit(1)

        if args.vm is None or args.path is None:
            print("vm and path are mandatory for add and remove actions", file=sys.stderr)
            sys.exit(1)

        if args.name is None:
            args.name = args.path.replace('/', '-')
            if args.name[0] == '-':
                args.name = args.name[1:]

    if args.action in ['wait', 'delete']:
        if args.vm is None:
            print("vm is mandatory for wait and delete actions", file=sys.stderr)
            sys.exit(1)

    if args.action == 'wait':
        start = time.time()
        while time.time() - start < args.timeout:
            # hubsharelib.vm_find() comes with a sleep wait, so we can just
            # spam it
            vms = hubsharelib.vm_find()
            for ip in vms.keys():
                if ip == args.vm or vms[ip]['name'] == args.vm:
                    print(ip + " is " + vms[ip]['name'] + " (" + vms[ip]['mac'] + ")")
                    sys.exit(0)

        print("Timeout waiting for " + args.vm, file=sys.stderr)
        sys.exit(1)

    if args.action == 'list':
        hub_confs = list()
        mfl = {'path': 4, 'name': 4, 'ip': 2, 'vm': 2, 'read_only': 8, 'guest_ok': 7}

        for scope in ['perm', 'temp']:
            for conf_file in os.listdir('/etc/samba/' + scope + '.conf.d'):
                ip = re.search(r'\d+\.\d+\.\d+\.\d+(?=\.conf)', conf_file).group(0)
                hub_confs.append(hubsharelib.HubConf(ip, perm=scope == 'perm'))

                for mx in mfl.keys():
                    for conf in hub_confs:
                        if mx in ['ip', 'vm']:
                            if len(getattr(conf, mx)) > mfl[mx]:
                                mfl[mx] = len(getattr(conf, mx))

                        for share in conf.shares:
                            if mx not in ['ip', 'vm']:
                                if len(str(share[mx])) > mfl[mx]:
                                    mfl[mx] = len(str(share[mx]))

        mfl_sum = 0
        for mx in mfl.keys():
            mfl[mx] += 1
            mfl_sum += mfl[mx]

        output_fields = ['vm', 'ip', 'name', 'path', 'read_only', 'guest_ok']

        # Output the shares
        for scope in ['perm', 'temp']:
            if scope == 'perm':
                print("#### Permanent Shares ####")
            else:
                print("#### Temporary Shares ####")

            sys.stdout.write("VM".ljust(mfl['vm']) + " | ")
            sys.stdout.write("IP".ljust(mfl['ip']) + " | ")
            sys.stdout.write("Name".ljust(mfl['name']) + " | ")
            sys.stdout.write("Path".ljust(mfl['path']) + " | ")
            sys.stdout.write("Read Only | Guest OK\n")
            sys.stdout.write("-" * (mfl_sum + ((len(output_fields) - 1) * 3)))
            sys.stdout.write('\n')

            for conf_file in hub_confs:
                if conf_file.perm == (scope == 'perm'):
                    for share in conf_file.shares:
                        for mx in output_fields:
                            if mx in ['ip', 'vm']:
                                sys.stdout.write(getattr(conf_file, mx).ljust(mfl[mx]))
                            else:
                                sys.stdout.write(str(share[mx]).ljust(mfl[mx]))

                            if mx == 'guest_ok':
                                sys.stdout.write('\n')
                            else:
                                sys.stdout.write(' | ')

            print("")

    if args.action == 'find':
        vms = hubsharelib.vm_find()

        print("IP              | MAC               | VM")
        print("---------------------------------------------")

        for ip in vms.keys():
            sys.stdout.write(ip.ljust(16) + '| ')
            sys.stdout.write(vms[ip]['mac'].ljust(18) + '| ')
            sys.stdout.write(vms[ip]['name'] + '\n')

    if args.action == 'add':
        conf_file = hubsharelib.HubConf(args.vm, perm=args.permanent)
        share = conf_file.add_share(args.name, path=args.path)
        if args.readonly:
            share['read_only'] = True

        if args.guest:
            share['guest_ok'] = True

        conf_file.save()

    if args.action == 'remove':
        conf_file = hubsharelib.HubConf(args.vm, perm=args.permanent)
        conf_file.del_share(args.name)
        conf_file.save()

    if args.action == 'delete':
        conf_file = hubsharelib.HubConf(args.vm, perm=args.permanent)
        conf_file.delete()

    if args.action == 'clean':
        mac_map = hubsharelib.get_mac_map()
        for scope in ['perm', 'temp']:
            conf_dir = '/etc/samba/' + scope + '.conf.d/'
            for conf_file in os.listdir(conf_dir):
                with open(conf_dir + conf_file, 'r') as f:
                    conf_data = f.read()

                vm = re.search(r'(?<=# VM: ).*', conf_data).group(0)
                mac = re.search(r'(?<=# MAC: ).*', conf_data).group(0)

                if mac not in mac_map.keys():
                    print("Removing " + conf_file + " from " + scope + " because MAC is no longer present")
                    hubsharelib.delete_conf(conf_dir + conf_file)
                elif mac_map[mac] != vm:
                    print("Removing " + conf_file + " from " + scope + " because VM name does not match")
                    hubsharelib.delete_conf(conf_dir + conf_file)

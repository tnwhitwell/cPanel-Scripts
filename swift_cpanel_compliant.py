#!/usr/bin/env python

from __future__ import print_function
import swiftclient
import swiftclient.exceptions
from datetime import datetime
import argparse
import sys
from os import environ
import threading
import time

conn = None

available_commands = {
  'put': {'function': 'action_put', 'min_args': 2},
  'get': {'function': 'action_get', 'min_args': 2},
  'ls': {'function': 'action_ls', 'min_args': 0},
  'mkdir': {'function': 'action_mkdir', 'min_args': 1},
  'chdir': {'function': 'action_chdir', 'min_args': 1},
  'rmdir': {'function': 'action_rmdir', 'min_args': 1},
  'delete': {'function': 'action_delete', 'min_args': 1},
}

local_directory = ''


def usage(command=None):
    print("""USAGE: swift_cpanel_compliant.py <command> <cwd> <command_args>
Example:
    swift_cpanel_compliant.py ls /home/tester""")


class uploadThread (threading.Thread):
    def __init__(self, threadID, name, container_name, local_file, remote_file):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.container_name = container_name
        self.local_file = local_file
        self.remote_file = remote_file

    def run(self):
        with open(self.local_file, 'r') as file_to_put:
            conn.put_object(self.container_name, self.remote_file, contents=file_to_put)


def action_put(container_name, local_file, remote_file):
    sys.stdout.write('Uploading')
    sys.stdout.flush()
    upThread = uploadThread(1, 'UploadThread', container_name, local_file, remote_file)
    upThread.start()
    while upThread.isAlive():
        upThread.join(1)
        time.sleep(5)
        sys.stdout.write('.')
        sys.stdout.flush()
    sys.stdout.write('\n')
    try:
        conn.head_object(container_name, remote_file)
        print('The object was successfully created')
    except swiftclient.exceptions.ClientException as e:
        if e.http_status == 404:
            print('The object was not found', file=sys.stderr)
        else:
            print('An error occurred: ', file=sys.stderr)
            print(e, file=sys.stderr)
        sys.exit(1)


def action_get(container_name, remote_file, local_file):
    try:
        resp_headers, obj_contents = conn.get_object(container_name, remote_file)
        with open(local_file, 'w') as local:
            local.write(obj_contents)
    except swiftclient.exceptions.ClientException as e:
        if e.http_status == 404:
            print('The object was not found', file=sys.stderr)
        else:
            print('Failed to get object with error: %s' % e, file=sys.stderr)
        sys.exit(1)


def action_ls(container_name, folder=None):
    dirperms = 'drwxr--r--'
    fileperms = '-rw-r--r--'
    outfmt = '%s 1 swift swift %s %s %s'
    if folder:
        if not folder.endswith('/'):
            folder = '%s/' % folder
        data = conn.get_container(container_name, prefix=folder)[1]
    else:
        data = conn.get_container(container_name)[1]
    sizelength = 0
    for object in data:
        bytes = str(object['bytes'])
        if len(bytes) > sizelength:
            sizelength = len(bytes)
    for object in data:
        if folder:
            object['name'] = object['name'].replace(folder, '')
        if '/' in object['name']:
            continue
        mtimeo = datetime.strptime(object['last_modified'], '%Y-%m-%dT%H:%M:%S.%f')
        mtime = mtimeo.strftime('%b %d %H:%M')
        perms = ''
        if object['content_type'] == 'application/directory':
            perms = dirperms
        else:
            perms = fileperms
        print(outfmt % (perms, str(object['bytes']).rjust(sizelength), mtime, object['name']))


def action_mkdir(container_name, remote_directory):
    conn.put_object(container_name, remote_directory, contents='', content_type='application/directory')


def action_chdir(container_name, remote_directory):
    print(remote_directory)


def action_rmdir(container_name, remote_directory):
    files = conn.get_container(container_name, prefix='%s' % remote_directory)[1]
    for filename in files:
        try:
            conn.delete_object(container_name, filename['name'])
        except swiftclient.exceptions.ClientException as e:
            print("Failed to delete the object with error: %s" % e, file=sys.stderr)
            sys.exit(1)


def action_delete(container_name, remote_file):
    try:
        conn.delete_object(container_name, remote_file)
    except swiftclient.exceptions.ClientException as e:
        print("Failed to delete the object with error: %s" % e, file=sys.stderr)
        sys.exit(1)


def getOptions(args=None, error=None):
    parser = argparse.ArgumentParser(
        description='cPanel Custom backup destination for Openstack Swift')

    default_key = None
    for k in ('PASSWORD', 'ST_KEY'):
        try:
            default_key = environ[k]
            break
        except KeyError:
            pass

    parser.add_argument('command_args',
                        type=str, nargs='+', help='Arguments to run')
    parser.add_argument('-U', '--user', dest='user',
                        default=environ.get('ST_USER'),
                        help='User name for obtaining an auth token.')
    parser.add_argument('-K', '--key', dest='key',
                        default=default_key,
                        help='Key for obtaining an auth token.')
    parser.add_argument('-c', '--container', dest='container',
                        help='Swift container to use', required=True)
    parser.add_argument('-A', '--auth', dest='authurl',
                        default=environ.get('ST_AUTH'),
                        help='URL for obtaining an auth token.')
    if error:
        parser.print_usage()
        print('error: %s' % error, file=sys.stderr)
        sys.exit(1)
    out = vars(parser.parse_args(args))
    for k in ('user', 'key', 'authurl'):
        if not out[k]:
            getOptions(error='%s not provided as argument or environment' % k.upper())
    return out


def splitCommandArgs(args):
    out = {}
    out['command'] = args[0]
    out['pwd'] = args[1]
    out['command_args'] = args[2:]
    return out


if __name__ == '__main__':
    options = getOptions(sys.argv[1:])
    conn = swiftclient.Connection(
            user=options['user'],
            key=options['key'],
            authurl=options['authurl'],
    )
    commandline = splitCommandArgs(options['command_args'])
    command = commandline['command']
    if command in available_commands:
        no_args = len(commandline['command_args'])
        min_args = available_commands[command]['min_args']
        if no_args < min_args:
            getOptions(error='Too few arguments provided for '
                             '%s - at least %s required, %s provided.' % (command, min_args, no_args))
            sys.exit(1)
        function = available_commands[command]['function']
        globals()[function](options['container'], *commandline['command_args'])

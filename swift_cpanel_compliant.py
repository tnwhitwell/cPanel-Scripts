#!/usr/bin/env python

from __future__ import print_function
import swiftclient
import swiftclient.exceptions
from datetime import datetime
import sys
import os
import threading
import time


memstore_user = ''
memstore_key = os.environ['PASSWORD']
container_name = ''

conn = None

available_commands = {
  'put': 'action_put',
  'get': 'action_get',
  'ls': 'action_ls',
  'mkdir': 'action_mkdir',
  'chdir': 'action_chdir',
  'rmdir': 'action_rmdir',
  'delete': 'action_delete'
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


def action_put(local_file, remote_file):
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


def action_get(remote_file, local_file):
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


def action_ls(folder=None):
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


def action_mkdir(remote_directory):
    conn.put_object(container_name, remote_directory, contents='', content_type='application/directory')


def action_chdir(remote_directory):
    print(remote_directory)


def action_rmdir(remote_directory):
    files = conn.get_container(container_name, prefix='%s' % remote_directory)[1]
    for filename in files:
        try:
            conn.delete_object(container_name, filename['name'])
        except swiftclient.exceptions.ClientException as e:
            print("Failed to delete the object with error: %s" % e, file=sys.stderr)
            sys.exit(1)


def action_delete(remote_file):
    try:
        conn.delete_object(container_name, remote_file)
    except swiftclient.exceptions.ClientException as e:
        print("Failed to delete the object with error: %s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print('some arguments must be missing!', file=sys.stderr)
    memstore_user = sys.argv[-1]
    container_name = sys.argv[-2]
    if memstore_key == '':
        print('Password must be set', file=sys.stderr)
    if memstore_user == '':
        print('Username must be set', file=sys.stderr)
    if container_name == '':
        print('Container name (Remote Host) must be set', file=sys.stderr)
    conn = swiftclient.Connection(
            user=memstore_user,
            key=memstore_key,
            authurl='https://auth.storage.memset.com/v1.0',
    )
    with open('/tmp/custom_backup_args.txt', 'a') as log:
        log.write('%s\n' % str(sys.argv))
    args = sys.argv[1:]
    command = ''
    if len(args) < 2:
        usage()
    if args[0] in available_commands:
        function = available_commands[args[0]]
        local_directory = args[1]
        function_args = args[2:-2]
        globals()[function](*function_args)

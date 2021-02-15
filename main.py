#!/usr/bin/env python
#
# Certbot docker script
#
# By default, first new certificates are requested, then updates and pending
# certificates daily at 3 am. Useful to run as on Docker e.g. in combination
# with HAProxy.
#
# Configuration uses environment variables:
#   CERTBOT_EMAIL             Email address (default the empty string)
#   CERTBOT_DOMAINS           Whitespace-separated list of domains to request
#   CERTBOT_OUTPUT_DIRECTORY  Where to put PEM files with key+cert (default /certs)
#   CERTBOT_TOUCH_FILE        File to touch when certificates changed
#   CERTBOT_DISABLED          Set to 1 to disable certbot (default 0)
#   CERTBOT_DHPARAM_BITS      Number of bits for DH parameters (default 2048)
#
# The touch file can be used to trigger a restart of the webserver running
# in a different container, if you use a shared volume.
#
# Note that you can set CERTBOT_DISABLED=1 during development, if you do not have
# global DNS entries.
#
# Also, before the very first certificate is obtained from letsencrypt, a dummy
# certificate is generated. If this wouldn't happen, most webservers would fail
# to start at all, and the web-based letsencrypt verification process would fail.
# When a new certificate is available, a webserver like HAProxy will pickup the
# proper one.
#
# If you run this script with an argument, it will do the process once and exit,
# but this may be subject to change.
#
import datetime
import fnmatch
import os
import subprocess
import sys
import time

ACME_SERVER = 'https://acme-v02.api.letsencrypt.org/directory'
CERTBOT_DIRECTORY = '/etc/letsencrypt/live'

def run_process(header, args):
  print('===============================================================================')
  print(header)
  print('===============================================================================')

  sys.stdout.flush()
  ec = subprocess.call(args)

  print(args[0] + ' exit code ' + str(ec))
  print('')

def run_certbot_certonly(domain, email):
  run_process('Getting certificate for ' + domain, ['certbot', 'certonly', '--standalone',
    '--agree-tos', '--noninteractive', '--text', '--server', ACME_SERVER, '--expand',
    '--preferred-challenges', 'http-01', '--email', email, '-d', domain])

def run_certbot_renew():
  post_hook = sys.executable + ' ' + sys.argv[0] + ' post-hook'
  run_process('Renewing certificates', ['certbot', 'renew', '--post-hook', post_hook])

def get_certificates():
  if os.getenv('CERTBOT_DISABLED', '0') != '1':
    email = os.getenv('CERTBOT_EMAIL', '')
    for domain in os.environ['CERTBOT_DOMAINS'].split():
      run_certbot_certonly(domain, email)
  else:
    print('Skipping official certificates because CERTBOT_DISABLED is 1')

def ensure_output_directory():
  output_directory = os.getenv('CERTBOT_OUTPUT_DIRECTORY', '/certs')
  if not os.path.exists(output_directory):
    os.makedirs(output_directory)
  return output_directory

def concat_certificates():
  if not os.path.exists(CERTBOT_DIRECTORY): return
  output_directory = ensure_output_directory()
  for name in os.listdir(CERTBOT_DIRECTORY):
    path = os.path.join(CERTBOT_DIRECTORY, name)
    if os.path.isdir(path):
      outpath = os.path.join(output_directory, name + '.pem')
      with open(outpath, 'w') as fo:
        for name in ['fullchain.pem', 'privkey.pem']:
          with open(os.path.join(path, name), 'r') as fi:
            fo.write(fi.read())
            fo.write('\n')
      append_dhparams(outpath)

def append_dhparams(path):
  # appends newly generated DH params to file (against LOGJAM)
  bits = os.getenv('CERTBOT_DHPARAM_BITS', '2048')
  dhparam_path = '/tmp/dhparam.tmp'
  run_process('Generating DH parameters', ['openssl', 'dhparam', '-out', dhparam_path, bits])
  with open(path, 'a') as fo:
    with open(dhparam_path, 'r') as fi:
      fo.write(fi.read())
      fo.write('\n')
  os.unlink(dhparam_path)

def create_or_remove_localhost_certificate():
  output_directory = ensure_output_directory()
  pems = len(fnmatch.filter(os.listdir(output_directory), '*.pem'))
  path = os.path.join(output_directory, 'localhost.pem')
  if pems == 0:
    run_process('Generating localhost certificate', ['openssl', 'req', '-x509',
      '-newkey', 'rsa:2048', '-nodes', '-keyout', path, '-out', path,
      '-subj', '/CN=localhost'])
    append_dhparams(path)
  elif pems > 1 and os.path.isfile(path):
    os.unlink(path)

def touch_file():
  path = os.getenv('CERTBOT_TOUCH_FILE')
  if path:
    with open(path, 'a'):
      os.utime(path, None)

def run_post():
  concat_certificates()
  create_or_remove_localhost_certificate()
  touch_file()

def run_main():
  get_certificates()
  run_post()
  while True:
    now = datetime.datetime.now()
    renew_time = now + datetime.timedelta(days=1)
    renew_time = renew_time.replace(hour=3, minute=0, second=0, microsecond=0)
    time.sleep((renew_time - now).total_seconds())
    run_certbot_renew()

if __name__ == '__main__':
  if len(sys.argv) > 1:
    run_post()
  else:
    run_main()

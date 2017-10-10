import datetime
import fnmatch
import os
import subprocess
import sys
import time

ACME_SERVER = 'https://acme-v01.api.letsencrypt.org/directory'
CERTBOT_DIRECOTRY = '/etc/letsencrypt/live'

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
  email = os.getenv('CERTBOT_EMAIL', '')
  for domain in os.environ['CERTBOT_DOMAINS'].split():
    run_certbot_certonly(domain, email)

def ensure_output_directory():
  output_directory = os.getenv('CERTBOT_OUTPUT_DIRECTORY', '/certs')
  if not os.path.exists(output_directory):
    os.makedirs(output_directory)
  return output_directory

def concat_certificates():
  output_directory = ensure_output_directory()
  for name in os.listdir(CERTBOT_DIRECOTRY):
    path = os.path.join(CERTBOT_DIRECOTRY, name)
    if os.path.isdir(path):
      with open(os.path.join(output_directory, name + '.pem'), 'w') as fo:
        for name in ['fullchain.pem', 'privkey.pem']:
          with open(os.path.join(path, name), 'r') as fi:
            fo.write(fi.read())
            fo.write('\n')

def create_or_remove_localhost_certificate():
  output_directory = ensure_output_directory()
  pems = len(fnmatch.filter(os.listdir(output_directory), '*.pem'))
  path = os.path.join(output_directory, 'localhost.pem')
  if pems == 0:
    run_process('Generating localhost certificate', ['openssl', 'req', '-x509',
      '-newkey', 'rsa:2048', '-nodes', '-keyout', path, '-out', path,
      '-subj', '/CN=localhost'])
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

if len(sys.argv) > 1:
  run_post()
else:
  run_main()

#!/usr/bin/python3

import pwgen
import os
import shutil
import subprocess
import sys
import textwrap
import time

# Install mailman as far as possible without /var/ volume to speed up
# container startup later:

os.mkdir("/mailman-venv")
python3_version = "python3"
if "extra_mailman_python_version" in os.environ:
    python3_version = "python" + os.environ[
        "extra_mailman_python_version"]
subprocess.check_output(["bash",
    "-c", "source /root/.bashrc; virtualenv /mailman-venv"])

# Create folders and get source code:
if not os.path.exists("/opt"):
    os.mkdir("/opt")
if not os.path.exists("/opt/mailman"):
    os.mkdir("/opt/mailman/")
subprocess.check_output(["git",
    "clone",
    "https://gitlab.com/mailman/mailman-bundler.git"],
    cwd="/opt/mailman/")
os.chdir("/opt/mailman/mailman-bundler/")

# Set buildout.cfg to production mode:
contents = None
with open("/opt/mailman/mailman-bundler/buildout.cfg", "r") as f:
    contents = f.read()
contents_lines = contents.replace("\r\n", "\n").split("\n")
new_contents = ""
for line in contents_lines:
    if line.startswith("deployment ="):
        new_contents += "\ndeployment = production"
    else:
        new_contents += "\n" + line
with open("/opt/mailman/mailman-bundler/buildout.cfg", "w") as f:
    f.write(new_contents)

# Alter secret key, ALLOWED_HOSTS, USE_INTERNAL_AUTH and
# USE_SSL for production:
contents = None
with open("/opt/mailman/mailman-bundler/mailman_web/production.py",
        "r") as f:
    contents = f.read()
contents_lines = contents.replace("\r\n", "\n").split("\n")
new_contents = ""
for line in contents_lines:
    if line.startswith("SECRET_KEY ="):
        new_contents += "\nSECRET_KEY = '" + pwgen.pwgen(
            pw_length=30) + "'"
    elif line.startswith("ALLOWED_HOSTS ="):
        new_contents += "\nALLOWED_HOSTS = [\"*\"]"
    elif line.startswith("USE_INTERNAL_AUTH ="):
        new_contents += "\nUSE_INTERNAL_AUTH = True"
    else:
        new_contents += "\n" + line
new_contents += "\nUSE_SSL = False"
with open("/opt/mailman/mailman-bundler/mailman_web/production.py",
        "w") as f:
    f.write(new_contents)

# Change production config to use sqlite3:
contents = None
with open("/opt/mailman/mailman-bundler/mailman_web/production.py",
        "r") as f:
    contents = f.read()
contents_lines = contents.replace("\r\n", "\n").split("\n")
new_contents = ""
skip_until_block_end = False
saw_bracket_close = False
for line in contents_lines:
    if line.startswith("DATABASES ="):
        new_contents += """
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(VAR_DIR, 'mailman-web', 'mailman-web.sqlite'),
    }
}
        """
        skip_until_block_end = True
        saw_bracket_close = False
    elif skip_until_block_end and line.strip() == "}":
        saw_bracket_close = True
    elif skip_until_block_end and line.strip() != "}" and saw_bracket_close:
        skip_until_block_end = False
        new_contents += "\n" + line
    elif not skip_until_block_end:
        new_contents += "\n" + line
with open("/opt/mailman/mailman-bundler/mailman_web/production.py",
        "w") as f:
    f.write(new_contents)

# Create folder for logging:
if not os.path.exists("/var"):
    os.mkdir("/var")
if not os.path.exists("/var/log"):
    os.mkdir("/var/log")
if not os.path.exists("/var/log/mailman-web"):
    os.mkdir("/var/log/mailman-web/")

# Run the buildout process, including the gunicorn install:
result = subprocess.call(["buildout"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
result = subprocess.call(["buildout", "install",
    "gunicorn"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)

# Install dj-static, psycopg2 system-wide
result = subprocess.call(["pip3",
    "install", "dj-static", "psycopg2"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
result = subprocess.call(["pip",
    "install", "dj-static", "psycopg2"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)

# Install dj-static, psycopg2 in virtualenv of mailman:
def mailman_venv():
    for f in os.listdir("/opt/mailman/mailman-bundler"):
        if f.startswith("venv-"):
            return "/opt/mailman/mailman-bundler/" + f
    raise RuntimeError("failed to find venv of mailman")
result = subprocess.call(["bash",
    "-c", "source /root/.bashrc; " +
    "source " + mailman_venv() + "/bin/activate; " +
    "pip install dj-static psycopg2"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
# Run mailman post-update:
subprocess.check_output([
    "./bin/mailman-post-update"],
    cwd="/opt/mailman/mailman-bundler/")

# Start mailman to generate config:
print("Launching mailman...", flush=True)
os.chdir("/opt/mailman/mailman-bundler/")
assert(os.path.exists("./bin/mailman"))
result = subprocess.call(["bash",
    "-c", "./bin/mailman start"],
    cwd="/opt/mailman/mailman-bundler/",
    shell=True, stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
time.sleep(5)
print("Launching hyperkitty...", flush=True)
p = subprocess.Popen(["./bin/mailman-web-django-admin",
    "runserver", "127.0.0.1:8000"],
    cwd="/opt/mailman/mailman-bundler/")
time.sleep(10)

# Terminate mailman again:
print("Terminating hyperkitty...", flush=True)
try:
    subprocess.call(["kill", str(p.pid)])
except Exception as e:
    pass
time.sleep(5)
try:
    p.kill()
except Exception as e:
    pass
print("Termating mailman...", flush=True)
subprocess.call(["./bin/mailman", "stop"], timeout=15)
time.sleep(3)

shutil.copytree("/opt/mailman/mailman-bundler/var/",
    "/opt/mailman/mailman-bundler-var-default")
os._exit(0)



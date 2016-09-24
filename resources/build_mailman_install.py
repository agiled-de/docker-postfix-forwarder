#!/usr/bin/python3

import os
import shutil
import subprocess
import sys
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

if not os.path.exists("/opt"):
    os.mkdir("/opt")
if not os.path.exists("/opt/mailman"):
    os.mkdir("/opt/mailman/")
subprocess.check_output(["git",
    "clone",
    "https://gitlab.com/mailman/mailman-bundler.git"],
    cwd="/opt/mailman/")
os.chdir("/opt/mailman/mailman-bundler/")
result = subprocess.call(["buildout"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
result = subprocess.call(["buildout", "install",
    "gunicorn"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)

# Install dj-static system-wide
result = subprocess.call(["pip3",
    "install", "dj-static"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
result = subprocess.call(["pip",
    "install", "dj-static"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)

# Install dj-static in virtualenv of mailman:
def mailman_venv():
    for f in os.listdir("/opt/mailman/mailman-bundler"):
        if f.startswith("venv-"):
            return "/opt/mailman/mailman-bundler/" + f
    raise RuntimeError("failed to find venv of mailman")
result = subprocess.call(["bash",
    "-c", "source /root/.bashrc; " +
    "source " + mailman_venv() + "/bin/activate; " +
    "pip install dj-static"],
    stderr=subprocess.STDOUT)
if result != 0:
    sys.exit(1)
# RUn mailman post-update:
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



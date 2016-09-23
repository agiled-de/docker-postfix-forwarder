#!/usr/bin/python3

import os
import shutil
import subprocess
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
subprocess.check_output([
    "./bin/mailman-post-update"],
    cwd="/opt/mailman/mailman-bundler/")

# Start mailman to generate config:
subprocess.check_output(["./bin/mailman", "start"],
    cwd="/opt/mailman/mailman-bundler/")
time.sleep(5)
p = subprocess.Popen(["./bin/mailman-web-django-admin",
    "runserver", "0.0.0.0:8000"],
    cwd="/opt/mailman/mailman-bundler/")
time.sleep(10)

# Terminate mailman again:
try:
    subprocess.call(["kill", str(p.pid)])
except Exception as e:
    pass
time.sleep(5)
try:
    p.kill()
except Exception as e:
    pass
subprocess.call(["./bin/mailman", "stop"])
time.sleep(3)

shutil.copytree("/opt/mailman/mailman-bundler/var/",
    "/opt/mailman/mailman-bundler-var-default")


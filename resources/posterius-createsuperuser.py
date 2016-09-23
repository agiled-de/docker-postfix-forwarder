#!/usr/bin/python3
from __future__ import print_function

import argparse
import logging
import multiprocessing
import os
import pty
import queue
import subprocess
import shlex
import sys
import threading
import time
import traceback
import yaml

# If arguments are provided, work as  PTY wrapper:
if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "pty":
    pty.spawn(sys.argv[2:])
    sys.exit(0)

# Process wrapper:
class InteractiveTerminalWrapper(object):
    def __init__(self, cmd):
        if not hasattr(cmd, "append"):
            # Convert to list:
            cmd = [ cmd ]
        self.cmd = cmd
        self._read_lines = []
        self._process_was_terminated = False
        self.install_thread = threading.Thread(target=self._run_install)
        self.install_thread.start() 

    def _run_install(self):
        script_name = os.path.abspath(__file__)
        self.process = None
        _cmd = self.cmd

        # Launch the process with a pty wrapper:
        try:
            _cmd = [path_arg.encode("utf-8") for path_arg in _cmd]
        except AttributeError:
            pass
        self.process = subprocess.Popen([sys.executable,
            "-c", "import pty; import sys; " +\
            "pty.spawn(sys.argv[1:])"] + _cmd, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        try:
            # Threaded line reader to avoid blocking:
            q = queue.Queue()
            class StdoutReaderThread(threading.Thread):
                def __init__(self, process):
                    super().__init__()
                    self.process = process

                def run(self):
                    try:
                        while True:
                            q.put(self.process.stdout.read(1))
                    except (ValueError, OSError):
                        return
            read_thread = StdoutReaderThread(self.process)
            read_thread.start()

            # Read line for line and report back to parent:
            contents = b""
            last_read_time = time.monotonic()
            while self.process.poll() == None:
                new_contents = None
                try:
                    new_contents = q.get(timeout=5)
                except queue.Empty:
                    if len(contents) == 0:
                        continue
                    new_contents = b"\n"
                if new_contents == None or len(new_contents) == 0:
                    break
                if new_contents == b"\n":
                    contents = contents + new_contents
                    self._read_lines.append(contents)
                    contents = b""
                else:
                    contents += new_contents

            try:
                self.process.stdout.close()
            except Exception as e:
                pass
        except Exception as e:
            print("ERROR during stdout read: " + str(e), file=sys.stderr)
            print(str(traceback.format_exc()))
            # Force process to terminate:
            self.process.terminate()
        finally:
            # Wait for process to terminate:
            try:
                self.process.wait()
            except Exception as e:
                pass

            self._process_was_terminated = True

    def write(self, data):
        try:
            data = data.encode("utf-8")
        except AttributeError:
            pass
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def readlines(self, timeout=None):
        # Some preparations:
        remaining_timeout = timeout
        start_time = time.monotonic()
        if not hasattr(self, "_iterator_line"):
            self._iterator_line = -1
        self._iterator_line += 1
        
        # Wait for new line:
        while len(self._read_lines) < self._iterator_line + 1 and \
                (timeout == None
                or (time.monotonic() - start_time) < remaining_timeout) and \
                not self._process_was_terminated:
            time.sleep(0.5)

        # If timeout exceeded with no new line, raise an error:
        if len(self._read_lines) < self._iterator_line + 1:
            if timeout != None:
                raise TimeoutError("readline timed out")
            raise EOFError("end of lines")

        # Return newest line:
        return self._read_lines[self._iterator_line]

    def lines(self):
        while True:
            try:
                lines = self.readlines()
            except EOFError:
                return
            if lines.endswith(b"\n"):
                lines = lines[:-1]
            for line in lines.split(b"\n"):
                yield line.decode("utf-8", "replace")

    def __iter__(self):
        class LinesIterator(object):
            def __init__(self, installer_obj):
                self.installer_obj = installer_obj
                self.lines_generator = self.installer_obj.lines()

            def __iter__(self):
                return self

            def __next__(self):
                return self.lines_generator.__next__()

            def next(self):
                return self.__next__()
        return LinesIterator(self)

argparser = argparse.ArgumentParser()
argparser.add_argument("user")
argparser.add_argument("password")
argparser.add_argument("email")
args = argparser.parse_args()

if len(args.user) <= 0:
    print("GRAVE ERROR - user is empty.", file=sys.stderr)
    sys.exit(1)

if len(args.password) <= 0:
    print("GRAVE ERROR - password is empty.", file=sys.stderr)
    sys.exit(1) 

if len(args.email) <= 0:
    print("GRAVE ERROR - e-mail is empty.", file=sys.stderr)
    sys.exit(1)

os.chdir("/opt/mailman/mailman-bundler/")
print("Superuser creation: launching mailman web admin...", flush=True)
installer = InteractiveTerminalWrapper(
    [ "./bin/mailman-web-django-admin", "createsuperuser" ])
lines = iter(installer)

print("Superuser creation: listening for output " +
    "interactively...", flush=True)

encountered_lines = []

class AbortThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.terminated = False

    def run(self):
        global encountered_lines
        total_s = 1
        while True:
            total_s += 1
            time.sleep(1)
            if self.terminated:
                return
            if total_s >= 30:
                print("ERROR: timeout for admin user creation. " +
                    "Total lines are: " + str(encountered_lines),
                    file=sys.stderr, flush=True)
                os._exit(1)
abrt_t = AbortThread()
abrt_t.start()

while True:
    line = next(lines)
    encountered_lines.append(line)
    if line.find("Username") >= 0:
        break
installer.write(args.user + "\n")
while True:
    line = next(lines)
    encountered_lines.append(line)
    if line.find("username is already taken") >= 0:
        print("NOTHING TO DO, superuser already exists.",
            flush=True)
        abrt_t.terminated = True
        os._exit(0)
    if line.find("Email") >= 0:
        break
installer.write(args.email + "\n")
while True:
    line = next(lines)
    encountered_lines.append(line)
    if line.find("Password") >= 0:
        break
installer.write(args.password + "\n")
while True:
    line = next(lines)
    encountered_lines.append(line)
    if line.find("Password") >= 0:
        break
installer.write(args.password + "\n")
abrt_t.terminated = True
time.sleep(5)
print("DONE.")
os._exit(0)


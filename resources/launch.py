#!/usr/bin/python3

import os
import shutil
import signal
import subprocess
import time

def setup():
    print ("[launch.py] *** SETUP STARTED... ***",
        flush=True)

    print ("[launch.py] Stopping postfix and syslog...",
        flush=True)

    os.system("service postfix stop")
    os.system("service syslog-ng stop")

    print ("[launch.py] Adding postfix and sasl users...",
        flush=True)

    subprocess.check_output(["adduser", "postfix", "sasl"])

    print ("[launch.py] Calling dpkg-reconfigure for postfix...",
        flush=True)


    os.system("bash -c \"DEBIAN_FRONTEND=noninteractive " +\
        "dpkg-reconfigure postfix\"")

    print ("[launch.py] Editing configs for settings...",
        flush=True)

    def virtual_domains():
        """ Domains we receive e-mail for, but which we don't actually accept
            for local storage (IMAP) but just for forwarding.
        """
        domains = set([(item.strip()).partition("=")[0].partition("@")[2] \
            for item in os.environ["MAIL_FORWARDS"].split(",")])
        domains.discard("")
        return domains

    def actual_domains():
        """ All domains for which we are the true final destination, that is
            no e-mail forwarding to external providers.
        """
        domains = set([item.strip()
            for item in os.environ["EMAIL_HOSTS"].split(",")])
        domains.discard("")
        for virtual in virtual_domains():
            domains.discard(virtual)
        return domains

    def all_domains():
        """ All domains for which we receive e-mail, no matter if it is
            handled locally as final destination or forwarded to an external
            provider.
        """
        vd = virtual_domains()
        ad = actual_domains()
        print("DEBUG VD: " + str(vd))
        print("DEBUG AD: " + str(ad))
        return vd.union(ad)

    def filter_file(name, filter_func):
        with open(name, "r") as f:
            contents = f.read()
            contents = contents.replace("\r\n", "\n")
        lines = contents.split("\n")
        lines = [filter_func(line) for line in lines]
        with open(name, "w") as f:
            f.write("\n".join(lines))

    def append_to_file(name, line):
        with open(name, "r") as f:
            contents = f.read()
        with open(name, "w") as f:
            f.write(contents + "\n" + line)

    def simplify(line):
        line = line.replace("\t", " ")
        while line.find("  ") >= 0:
            line = line.replace("  ", " ")
        assign_index = line.find("=")
        if assign_index > 0:
            line = line[:assign_index].rstrip() + line[assign_index:]
        return line.lstrip()

    # Require tls for external smtpd connections:
    def master_cf_tls(line):
        if (simplify(line).startswith("smtp inet") and
                simplify(line).endswith('smtpd')):
            return "smtp inet n - n - - smtpd\n" +\
                "  -o smtpd_enforce_tls=yes\n" +\
                "587 inet n - n - - smtpd\n" +\
                "  -o smtpd_enforce_tls=yes"
        elif not line.startswith("#"):
            # Remove chroot from services:
            parts = simplify(line).split(" ")
            if len(parts) >= 5 and parts[4] == "y":
                parts[4] = "n"
                return " ".join(parts)
        return line
    filter_file("/etc/postfix/master.cf", master_cf_tls)

    # Set mail origin and main hostname:
    main_mail = os.environ["MAILNAME"]
    def main_cf_main_mail(line):
        if simplify(line).startswith("myhostname="):
            return "myhostname= " + main_mail + "\n" + "myorigin= " + main_mail
        elif simplify(line).startswith("myorigin="):
            return ""
        return line
    filter_file("/etc/postfix/main.cf", main_cf_main_mail)

    # Configure TLS certs:
    def main_cf_tls(line):
        if "CERT_DIR" in os.environ:
            if simplify(line).startswith("smtpd_tls_cert_file="):
                return "smtpd_tls_cert_file=" + os.environ["CERT_DIR"] +\
                    "fullchain.pem"
            if simplify(line).startswith("smtpd_tls_key_file="):
                return "smtpd_tls_key_file=" + os.environ["CERT_DIR"] +\
                    "privkey.pem"
        if simplify(line).startswith("smtpd_use_tls="):
            return "smtpd_use_tls=yes"
        return line
    filter_file("/etc/postfix/main.cf", main_cf_tls)

    # Configure general SMTP relaying + sending settings:
    def main_cf_smtp_relaying(line):
        if simplify(line).startswith("smtpd_relay_restrictions="):
            return "smtpd_relay_restrictions=" +\
                "reject_authenticated_sender_login_mismatch " +\
                "permit_sasl_authenticated " +\
                "defer_unauth_destination permit_mynetworks"
        return line
    filter_file("/etc/postfix/main.cf", main_cf_smtp_relaying)

    # Configure non-virtual mail destinations:
    def main_cf_dest(line):
        if simplify(line).startswith("mydestination="):
            return "mydestination=" +\
                "localhost.localdomain, localhost, " +\
                ", ".join(all_domains())
        return line
    filter_file("/etc/postfix/main.cf", main_cf_dest)

    # Configure virtual mail domains:
    append_to_file("/etc/postfix/main.cf",
        "virtual_alias_domains = " + ", ".join(virtual_domains()) + "\n" +
        "virtual_alias_maps = hash:/etc/postfix/virtual\n")

    # Write /etc/postfix/virtual with virtual domain redirects / forwards:
    with open("/etc/postfix/virtual", "w") as f:
        combined_aliases = [item.strip() for item in os.environ[
            "MAIL_FORWARDS"].split(",")]
        
        alias_map = {}
        for alias in combined_aliases:
            source_part = alias.partition("=")[0]
            target_part = alias.partition("=")[2]
            if not source_part in alias_map:
                alias_map[source_part] = set()
            alias_map[source_part].add(target_part)

        # Write regular aliases:
        for alias_source in alias_map:
            target_line = ",".join(alias_map[alias_source])
            f.write(alias_source + " " + target_line + "\n") 

        # Write catch all:
        if "CATCH_ALL_TARGET_USER" in os.environ:
            catch_all = os.environ["CATCH_ALL_TARGET_USER"]
            for domain in all_domains():
                f.write("@" + domain + " " + os.environ[
                    "CATCH_ALL_TARGET_USER"] + "@" + main_mail + "\n")

    # Fix syslog config for docker use:
    def fix_syslog(line):
        if simplify(line).startswith("system()"):
            return "unix-stream(\"/dev/log\");"
        elif simplify(line).startswith("unix-stream"):
            return ""
        return line
    filter_file("/etc/syslog-ng/syslog-ng.conf", fix_syslog)

    # Enable SASL auth:
    append_to_file("/etc/postfix/main.cf",
        "smtpd_sasl_auth_enable = yes\n" +
        "smtpd_sasl_security_options = noanonymous\n" +
        "smtpd_sasl_local_domain = $myhostname\n" +
        "smtpd_sasl_path = smtpd\n" +
        "smtp_tls_security_level = dane\n" +
        "smtp_dns_support_level = dnssec\n" +
        "smtpd_sender_login_maps = " +
            "hash:/etc/postfix/controlled_envelope_senders\n")
    with open("/usr/lib/sasl2/smtpd.conf", "w") as f:
        f.write("pwcheck_method: saslauthd\n")
        f.write("mech_list: plain login\n")
    with open("/etc/postfix/sasl/smtpd.conf", "w") as f:
        f.write("pwcheck_method: saslauthd\n")
        f.write("mech_list: plain login\n")
    with open("/etc/postfix/controlled_envelope_senders", "w") as f:
        # Compute permissions:
        logins = [item.strip() for item in os.environ[
            "SMTP_LOGIN"].split(",")]
        forwarded = set([entry.strip().partition("=")[0] for entry in \
            os.environ["MAIL_FORWARDS"].split(",")])
        forwarded.discard("")
        mail_owners = dict()

        # Examine all SMTP logins:
        for login in logins:
            user = login.partition("=")[0]
            pw = login.partition("=")[2]

            # Allow this user to own any mails specified in MAIL_FORWARDS:
            addresses = [user + "@" + domain for domain in all_domains()]
            for address in addresses:
                if address in forwarded:
                    if not address in mail_owners:
                        mail_owners[address] = set()
                    mail_owners[address].add(user)
                    mail_owners[address].add(user + "@" +
                        os.environ["MAILNAME"])

            # Allow this user to own their name on the main mail domain:
            address = user + "@" + os.environ["MAILNAME"]
            if not address in mail_owners:
                mail_owners[address] = set()
            mail_owners[address].add(user)
            mail_owners[address].add(user + "@" + os.environ["MAILNAME"])

        # Write file:
        f.write("# Automatically computed SMTP SASL senders:\n")
        for address in mail_owners:
            f.write(address + " " + ", ".join(mail_owners[address]) + "\n")

    print ("[launch.py] Done editing configs.",
        flush=True)

    print ("[launch.py] Creating SMTP users....",
        flush=True)

    # Create user(s):
    uid = 1200
    with open("/tmp/smtp-newusers", "w") as f:
        logins = [item.strip() for item in os.environ["SMTP_LOGIN"].split(",")]
        for login in logins:
            user = login.partition("=")[0]
            pw = login.partition("=")[2]
            if user.find("/") >= 0 or user.find("..") >= 0 or\
                    user.find(":") >= 0:
                raise RuntimeError("invalid user name")
            if pw.find(":") >= 0:
                raise RuntimeError("colon in SMTP login password not supported")
            if not os.path.exists("/home/" + user): 
                os.mkdir("/home/" + user)
            line = user + ":" + pw + ":" + str(uid) + ":" +\
                str(uid) + ":SMTP user:/home/" + user + ":/bin/false"
            f.write(line + "\n")
            uid += 1
            # Format: username:passwd:uid:gid:gecos:homedir:shell
    try:
        subprocess.check_output(["newusers", "/tmp/smtp-newusers"])
    finally:
        os.remove("/tmp/smtp-newusers")

    print ("[launch.py] Setup complete.",
        flush=True)

# Prepare signal handlers:
global_info = {
    "sigterm_received" : False,
}
def handler_sigterm(signum, frame):
    global global_info
    global_info["sigterm_received"] = True
    print("[launch.py] SIGTERM received. Processing...", flush=True)
signal.signal(signal.SIGTERM, handler_sigterm)
def check_exit():
    global global_info
    if global_info["sigterm_received"]:
        print("[launch.py] Stopping services... (SIGTERM)", flush=True)
        os.system("service postfix stop")
        os.system("service syslog-ng stop")        
        print("[launch.py] All stopped. Terminating. (SIGTERM)", flush=True)
        sys.exit(0)

# Update configuration to newest settings:
setup()
check_exit()

# Announce that we will now launch everything:
print ("[launch.py] *** LAUNCH STARTED ***",
    flush=True)

# Start syslog and wait a bit for it to start:
print ("[launch.py] Launching syslog...",
    flush=True)
os.system("chmod 0775 /var/log")
subprocess.check_output(["syslog-ng", "--no-caps"])
time.sleep(5)
check_exit()

# Start SASL2 auth daemon:
print ("[launch.py] Launching saslauthd...",
    flush=True)
subprocess.check_output(["saslauthd", "-a", "shadow"])
time.sleep(5)
check_exit()

# Start postfix:
print ("[launch.py] Launching postfix...",
    flush=True)
if not os.path.exists("/var/spool/postfix/etc/services"):
    if not os.path.exists("/var/spool/postfix/"):
        os.mkdir("/var/spool/postfix")
    if not os.path.exists("/var/spool/postfix/etc"):
        os.mkdir("/var/spool/postfix/etc")
    shutil.copy("/etc/services", "/var/spool/postfix/etc/services")
subprocess.check_output(["postmap", "/etc/postfix/virtual"])
subprocess.check_output(["postmap",
    "/etc/postfix/controlled_envelope_senders"])
os.system("postfix start")
check_exit()

# Announce launch completion:
print ("[launch.py] Done. Everything should be running now.",
        flush=True)

# Endless loop to keep container running:
while True:
    check_exit()
    time.sleep(0.5)

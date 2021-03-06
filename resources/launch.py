#!/usr/bin/python3

import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time

def setup():
    print ("[launch.py] *** SETUP STARTED... ***",
        flush=True)

    print ("[launch.py] Stopping postfix and syslog...",
        flush=True)

    os.system("service postfix stop")
    os.system("service syslog-ng stop")

    enforce_tls = False
    if "POSTFIX_ENFORCE_TLS" in os.environ:
        value = os.environ["POSTFIX_ENFORCE_TLS"].strip().lower()
        if value == "yes" or value == "true" or value == "1":
            enforce_tls = True
    print ("[launch.py] Mail server will be configured to " +
        "enforce TLS for incoming mails: " + str (enforce_tls))

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
            for item in os.environ["POSTFIX_MAIL_FORWARDS"].split(",")])
        domains.discard("")
        return domains

    def actual_domains():
        """ All domains for which we are the true final destination, that is
            no e-mail forwarding to external providers.
        """
        domains = set([item.strip()
            for item in os.environ["POSTFIX_EMAIL_HOSTS"].split(",")])
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

    def config_set(key_name, key_value):
        found_it = True
        def replace_value(line):
            nonlocal found_it
            if found_it:
                return line
            if line.lstrip().startswith(key_name):
                key_name = line.lstrip()[len(key_name):].lstrip()
                if key_name.startswith("="):
                    found_it = True
                    return key_name + "=" + key_value
            return line
        if not found_it:
            append_to_file("/etc/postfix/master.cf",
                key_name + "=" + key_value)
        filter_file("/etc/postfix/master.cf", master_cf_tls)

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
            enforce_tls_line = "  -o smtpd_enforce_tls=yes\n"
            if not enforce_tls:
                enforce_tls_line = ""
            return "smtp inet n - n - - smtpd\n" +\
                enforce_tls_line +\
                "587 inet n - n - - smtpd\n" +\
                enforce_tls_line
        elif not line.startswith("#"):
            # Remove chroot from services:
            parts = simplify(line).split(" ")
            if len(parts) >= 5 and parts[4] == "y":
                parts[4] = "n"
                return " ".join(parts)
        return line
    filter_file("/etc/postfix/master.cf", master_cf_tls)

    # Set mail origin and main hostname:
    main_mail = os.environ["POSTFIX_MAILNAME"]
    def main_cf_main_mail(line):
        if simplify(line).startswith("myhostname="):
            return "myhostname= " + main_mail + "\n" + "myorigin= " +\
                main_mail
        elif simplify(line).startswith("myorigin="):
            return ""
        return line
    filter_file("/etc/postfix/main.cf", main_cf_main_mail)

    # Configure TLS certs:
    def main_cf_tls(line):
        if "POSTFIX_CERT_DIR" in os.environ:
            if simplify(line).startswith("smtpd_tls_cert_file="):
                return "smtpd_tls_cert_file=" + os.environ[
                    "POSTFIX_CERT_DIR"] +\
                    "fullchain.pem"
            if simplify(line).startswith("smtpd_tls_key_file="):
                return "smtpd_tls_key_file=" + os.environ[
                    "POSTFIX_CERT_DIR"] +\
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
                ", ".join(actual_domains())
        return line
    filter_file("/etc/postfix/main.cf", main_cf_dest)

    # Configure virtual mail domains:
    append_to_file("/etc/postfix/main.cf",
        "virtual_alias_domains = " + ", ".join(virtual_domains()) + "\n" +
        "virtual_alias_maps = hash:/etc/postfix/virtual\n")

    # Configure received message sizes to <=300mb:
    def main_cf_message_size_limit(line):
        if simplify(line).startswith("mailbox_size_limit") or \
                simplify(line).startswith("message_size_limit"):
            return "message_size_limit = 314572800"
        return line
    filter_file("/etc/postfix/main.cf", main_cf_message_size_limit)

    # Set some TLS security optoins:
    config_set("smtpd_tls_mandatory_protocols", "!SSLv2,!SSLv3")
    config_set("smtp_tls_mandatory_protocols", "!SSLv2,!SSLv3")
    config_set("smtpd_tls_protocols", "!SSLv2,!SSLv3")
    config_set("smtpd_tls_protocols", "!SSLv2,!SSLv3")
    config_set("smtpd_tls_exclude_ciphers",
        "aNULL, eNULL, EXPORT, DES, RC4, MD5, PSK, aECDH, " +
        "EDH-DSS-DES-CBC3-SHA, EDH-RSA-DES-CDC3-SHA, KRB5-DE5, CBC3-SHA")

    # Mailman-specific options if enabled:
    if "MAILMAN_ENABLE" in os.environ and (
            os.environ["MAILMAN_ENABLE"].lower() == "true" or
            os.environ["MAILMAN_ENABLE"].lower() == "on" or
            os.environ["MAILMAN_ENABLE"].lower() == "yes" or
            os.environ["MAILMAN_ENABLE"].lower() == "1"):
        config_set("recipient_delimiter", "+")
        append_to_file("/etc/postfix/main.cf", textwrap.dedent(
            """
            unknown_local_recipient_reject_code = 550
            owner_reuqest_special = no
 
            transport_maps =
                regexp:/opt/mailman/var/data/postfix_lmtp
            local_recipient_maps =
                regexp:/opt/mailman/var/data/postfix_lmtp
            relay_domains =
                regexp:/opt/mailman/var/data/postfix_domains
            """))
        

    # Write /etc/postfix/virtual with virtual domain redirects / forwards:
    with open("/etc/postfix/virtual", "w") as f:
        combined_aliases = [item.strip() for item in os.environ[
            "POSTFIX_MAIL_FORWARDS"].split(",")]
        
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
        if "POSTFIX_CATCH_ALL_TARGET_USER" in os.environ:
            catch_all = os.environ["POSTFIX_CATCH_ALL_TARGET_USER"]
            for domain in all_domains():
                f.write("@" + domain + " " + os.environ[
                    "POSTFIX_CATCH_ALL_TARGET_USER"] + "@" + main_mail + "\n")

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
        "smtpd_tls_security_level = may\n" +
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
            "POSTFIX_SMTP_LOGIN"].split(",")]
        forwarded = set([entry.strip().partition("=")[0] for entry in \
            os.environ["POSTFIX_MAIL_FORWARDS"].split(",")])
        forwarded.discard("")
        mail_owners = dict()

        # Examine all SMTP logins:
        for login in logins:
            user = login.partition("=")[0]
            pw = login.partition("=")[2]

            # Allow this user to own any mails specified in
            # POSTFIX_MAIL_FORWARDS:
            addresses = [user + "@" + domain for domain in all_domains()]
            for address in addresses:
                if address in forwarded:
                    if not address in mail_owners:
                        mail_owners[address] = set()
                    mail_owners[address].add(user)
                    mail_owners[address].add(user + "@" +
                        os.environ["POSTFIX_MAILNAME"])

            # Allow this user to own their name on the main mail domain:
            address = user + "@" + os.environ["POSTFIX_MAILNAME"]
            if not address in mail_owners:
                mail_owners[address] = set()
            mail_owners[address].add(user)
            mail_owners[address].add(user + "@" + os.environ[
                "POSTFIX_MAILNAME"])

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
        logins = [item.strip() for item in os.environ[
            "POSTFIX_SMTP_LOGIN"].split(",")]
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

    # Check if mailman is supposed to be used:
    if "MAILMAN_ENABLE" in os.environ and (
            os.environ["MAILMAN_ENABLE"].lower() == "true" or
            os.environ["MAILMAN_ENABLE"].lower() == "on" or
            os.environ["MAILMAN_ENABLE"].lower() == "yes" or
            os.environ["MAILMAN_ENABLE"].lower() == "1"):
        print("[launch.py] mailman is ENABLED. Checking mailman "
            "config presence...",
            flush=True)
        # Error if mailman config volume is missing:
        if not os.path.exists("/opt/mailman/"):
            print("[launch.py] ERROR: mailman config missing. "
                "Did you read docker-compose.yml.example and "
                "add the required volumes? THIS ERROR IS FATAL.",
                flush=True, file=sys.stderr)
            sys.exit(1)

        # Write correct mailman-extra.cfg for postfix:
        with open("/tmp/mailman-extra.cfg", "r") as f:
            mm_extra = f.read()
        with open("/opt/mailman/mailman-extra.cfg", "w") as f:
            f.write(mm_extra)

        while not os.path.exists("/opt/mailman/var/data"):
            print("[launch.py] ERROR: mailman config files missing. "
                "Make sure /opt/mailman/ volume is set up "
                "correctly. WILL RETRY IN 5 SECONDS...",
                flush=True, file=sys.stderr)
            time.sleep(5)
        if not os.path.exists("/opt/mailman/var/data/postfix_domains"):
            with open("/opt/mailman/var/data/postfix_domains", "w") as f:
                pass
        if not os.path.exists("/opt/mailman/var/data/postfix_lmtp"):
            with open("/opt/mailman/var/data/postfix_lmtp", "w") as f:
                pass

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


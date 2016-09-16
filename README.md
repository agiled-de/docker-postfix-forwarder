
# Simple auto-forwarding postfix mail server for docker

*Important:* this project is not affiliated with/endorsed by docker
whatsoever. Apparently this note is necessary for some legal people at
docker, don't blame me.

This is a simple SMTP server container which supports:

- receiving e-mails for your choice of domains, and then forwarding it
  to some behind-the-scenes address of an existing e-mail provider

- sending e-mails directly from this server using an SMTP login

- (optional) using let's encrypt certificates from a docker-mounted volume for
  signed valid TLS certificates for your mailserver

As a result, this container is the perfect companion for a well-configured,
simple e-mail setup to be able to send/receive from custom domains, while
leaving the IMAP storage to any trusted existing provider which you use
behind the scenes.

If you want truly independent mail including IMAP, look elsewhere.
If you just want your custom e-mail address for the outside world, while
being ok with using an existing e-mail provider behind the scenes for IMAP,
then you probably found what you are looking for!

# How does it work?

Adjust the docker-compose.yml with your domains, email names and forwards,
SMTP login password(s) and optionally let's encrypt certificate directory.
After doing that, just fire it up with ``` docker-compose up -d``` and you
should be having working e-mail!


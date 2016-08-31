
# Simple auto-forwarding SMTP server with valid let's encrypt TLS cert support

This is a simple SMTP server container which simply handles your choice of
domains, and then forwards the received e-mail to your choice of targets at
existing e-mail providers. It will also allow you to send e-mail through it
with a password, but it will never store received e-mail itself (just
forward).

If you use let's encrypt, you can also mount the let's encrypt certificates
into the container to be used for your e-mail server to have valid verifiable
TLS certificates for your SMTP server.

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


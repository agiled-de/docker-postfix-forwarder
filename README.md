
# Simple auto-forwarding postfix mail server for docker

*Important:* this project is not affiliated with/endorsed by docker
whatsoever. Apparently this note is necessary for some legal people at
docker, don't blame me.

This is a simple SMTP server container which simply handles your choice of
domains, and then forwards the received e-mail to your choice of targets at
existing e-mail providers.

Features:
- Easy setup of multiple domains, accounts and mail forwarding (this container
  is for forwarding on your custom domains only, it doesn't do IMAP!)
- Optional catch-all for non-existing target accounts where mail is sent to
- Optional TLS enforcement when receiving e-mails from other servers
- Simple setup for SMTP accounts to send e-mail through this server with
  a password
- (Optional) support for let's encrypt certificates to be used for the SMTP TLS
  to have properly signed certificates

This container is the perfect companion for a well-configured, simple e-mail
setup to be able to send/receive from custom domains, while leaving the IMAP
storage to any trusted existing provider which you use behind the scenes.
(If you want truly independent mail including IMAP, look elsewhere.)

# How does it work?

- Copy docker-compose.yml.example to docker.compose.yml

- Adjust the docker-compose.yml with your domains, email names and forwards,
  ... (the file contains comments that document all the available options)

- If you want to have proper valid TLS certificates and you're using let's
  encrypt, you can add the certificate directory as a volume in
  docker-compose.yml

After doing that, open a terminal, change to the directory where the
docker-compose.yml is located and launch it with ``` docker-compose up -d```.

To check for possible problems and errors, open a terminal, change to the
directory where the docker-compose.yml is located and use the command
``` docker-compose logs```.

## License

```
Copyright (c) 2016, agiled.de

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
```


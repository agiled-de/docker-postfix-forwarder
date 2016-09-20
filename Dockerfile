
FROM ubuntu:16.04

# Uncomment & fill if current mailman requires another python version:
ENV extra_mailman_python_exact_version="3.4.5"
ENV extra_mailman_python_version="3.4"

RUN apt-get update --fix-missing && apt-get upgrade -y
RUN apt-get clean && apt-get update --fix-missing
RUN apt-get install -y curl
RUN apt-get install -y postfix syslog-ng
RUN apt-get install -y libsasl2-2 sasl2-bin
RUN apt-get install -y vim-common netcat

# Versioning access to git and bzr (mailman):
RUN apt-get install -y bzr git

# Python 3 basics & tox:
RUN apt-get install -y bash python3 python3-venv python3-pip
RUN pip3 install tox

# Provide a way to install multiple Python versions:
RUN apt-get install -y curl
RUN pip3 install tox
RUN apt-get install -y libssl-dev libbz2-dev libreadline-dev libsqlite3-dev
ADD ./resources/python_install.sh /tmp/python_install.sh
RUN bash /tmp/python_install.sh

EXPOSE 25
EXPOSE 587

CMD python3 /launch.py


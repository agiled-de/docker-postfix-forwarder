
FROM ubuntu:16.04

# Basics & postfix:
RUN apt-get update --fix-missing && apt-get upgrade -y
RUN apt-get clean && apt-get update --fix-missing
RUN apt-get install -y curl
RUN apt-get install -y postfix syslog-ng
RUN apt-get install -y libsasl2-2 sasl2-bin
RUN apt-get install -y vim-common netcat

# SMTP:
EXPOSE 25
EXPOSE 587

CMD python3 /launch.py


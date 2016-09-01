
FROM ubuntu:16.04

RUN apt-get update --fix-missing && apt-get upgrade -y
RUN apt-get clean && apt-get update --fix-missing
RUN apt-get install -y psmisc
RUN apt-get install -y postfix syslog-ng
RUN apt-get install -y libsasl2-2 sasl2-bin
#RUN apt-get install -y dovecot dovecot-pgsql postgresql
RUN apt-get install -y bash python3
RUN apt-get install -y vim-common netcat

EXPOSE 25
EXPOSE 587

CMD python3 /launch.py


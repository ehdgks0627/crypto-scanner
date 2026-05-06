FROM alpine:3.20.3

RUN apk add --no-cache openssh openssl python3 shadow \
  && adduser -D -s /bin/sh testbed \
  && echo "testbed:testbed" | chpasswd \
  && mkdir -p /home/testbed/.ssh /run/sshd \
  && chown -R testbed:testbed /home/testbed/.ssh

COPY services/ssh/sshd_config /etc/ssh/sshd_config
COPY services/ssh/entrypoint.sh /usr/local/bin/testbed-ssh-entrypoint
COPY agent /opt/testbed-agent

RUN chmod +x /usr/local/bin/testbed-ssh-entrypoint

EXPOSE 22 9100

ENTRYPOINT ["testbed-ssh-entrypoint"]

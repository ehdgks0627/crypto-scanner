#!/bin/sh
set -eu

if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
  ssh-keygen -t rsa -b 2048 -N "" -f /etc/ssh/ssh_host_rsa_key >/dev/null
fi
if [ ! -f /etc/ssh/ssh_host_ecdsa_key ]; then
  ssh-keygen -t ecdsa -b 256 -N "" -f /etc/ssh/ssh_host_ecdsa_key >/dev/null
fi
if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
  ssh-keygen -t ed25519 -N "" -f /etc/ssh/ssh_host_ed25519_key >/dev/null
fi
if [ ! -f /etc/ssh/ssh_host_dsa_key ]; then
  ssh-keygen -t dsa -N "" -f /etc/ssh/ssh_host_dsa_key >/dev/null 2>&1 || true
fi

if [ ! -f /home/testbed/.ssh/authorized_keys ]; then
  ssh-keygen -t rsa -b 2048 -N "" -f /home/testbed/.ssh/id_rsa >/dev/null
  ssh-keygen -t ecdsa -b 256 -N "" -f /home/testbed/.ssh/id_ecdsa >/dev/null
  ssh-keygen -t ed25519 -N "" -f /home/testbed/.ssh/id_ed25519 >/dev/null
  cat /home/testbed/.ssh/id_*.pub > /home/testbed/.ssh/authorized_keys
  chown -R testbed:testbed /home/testbed/.ssh
fi

python3 /opt/testbed-agent/mock_agent.py &
exec /usr/sbin/sshd -D -e

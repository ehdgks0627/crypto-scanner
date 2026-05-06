FROM python:3.12-alpine

RUN apk add --no-cache openssl

WORKDIR /opt/testbed-agent

RUN mkdir -p \
  /etc/api-gateway/trust \
  /etc/api-gateway/jwks \
  /var/lib/oidc \
  /etc/saml \
  /etc/registry \
  /var/lib/vault/transit \
  /etc/backup \
  /opt/legacy-java/conf

CMD ["python", "/opt/testbed-agent/mock_agent.py"]

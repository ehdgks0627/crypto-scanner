FROM alpine:3.20.3

RUN apk add --no-cache bash openssl

COPY scripts/check_env.sh /usr/local/bin/testbed-check-env

RUN chmod +x /usr/local/bin/testbed-check-env

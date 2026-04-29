FROM strongx509/strongswan@sha256:f35be40ef1b2f3a08ab50d2c9d6ee6697d57b00b4e045b2cde15d45b8a6c7e0c

COPY services/ipsec/entrypoint.sh /usr/local/bin/testbed-ipsec-entrypoint

RUN chmod +x /usr/local/bin/testbed-ipsec-entrypoint

ENTRYPOINT ["testbed-ipsec-entrypoint"]

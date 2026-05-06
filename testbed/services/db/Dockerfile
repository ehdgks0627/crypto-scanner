FROM postgres:16.6

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 ca-certificates openssl \
  && rm -rf /var/lib/apt/lists/*

COPY agent /opt/testbed-agent
COPY services/db/entrypoint.sh /usr/local/bin/testbed-db-entrypoint

RUN chmod +x /usr/local/bin/testbed-db-entrypoint

EXPOSE 5432 9100

ENTRYPOINT ["testbed-db-entrypoint"]
CMD ["postgres"]

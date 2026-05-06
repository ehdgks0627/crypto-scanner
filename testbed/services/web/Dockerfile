FROM nginx:1.27.3-alpine

RUN apk add --no-cache openssl python3

COPY services/web/nginx.conf /etc/nginx/nginx.conf
COPY services/web/index.html /usr/share/nginx/html/index.html
COPY agent /opt/testbed-agent
COPY services/web/entrypoint.sh /usr/local/bin/testbed-web-entrypoint

RUN chmod +x /usr/local/bin/testbed-web-entrypoint

EXPOSE 443 9100

ENTRYPOINT ["testbed-web-entrypoint"]

FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27.3-alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY generate-self-signed-cert.sh /docker-entrypoint.d/10-generate-self-signed-cert.sh
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
EXPOSE 443

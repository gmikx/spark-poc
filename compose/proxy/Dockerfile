FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY 40-selfsigned.sh /docker-entrypoint.d/40-selfsigned.sh
RUN chmod +x /docker-entrypoint.d/40-selfsigned.sh

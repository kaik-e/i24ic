FROM nginx:alpine

RUN apk add --no-cache openssl

# Generate self-signed certificate for testing
RUN mkdir -p /etc/nginx/certs && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/certs/selfsigned.key \
    -out /etc/nginx/certs/selfsigned.crt \
    -subj "/C=US/ST=State/L=City/O=Test/CN=localhost"

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

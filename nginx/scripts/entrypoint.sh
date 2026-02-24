#!/usr/bin/env sh
set -eu

mkdir -p /certs /nginx-state /etc/nginx/conf.d

if [ ! -f /certs/fullchain.pem ] || [ ! -f /certs/privkey.pem ]; then
  echo "[nginx] TLS certs not found in /certs. Generating temporary self-signed cert."
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout /certs/privkey.pem \
    -out /certs/fullchain.pem \
    -subj "/CN=localhost"
fi

if [ -f /nginx-state/setup_complete ]; then
cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 8080;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate /certs/fullchain.pem;
    ssl_certificate_key /certs/privkey.pem;

    client_max_body_size 25m;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /static/ {
        alias /static/;
    }

    location /media/ {
        alias /media/;
    }
}
EOF
else
cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 8080;
    server_name _;

    client_max_body_size 25m;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto http;
    }

    location /static/ {
        alias /static/;
    }

    location /media/ {
        alias /media/;
    }
}

server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate /certs/fullchain.pem;
    ssl_certificate_key /certs/privkey.pem;

    client_max_body_size 25m;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /static/ {
        alias /static/;
    }

    location /media/ {
        alias /media/;
    }
}
EOF
fi

exec "$@"

# Multi-stage build for cookbook static website
# Stage 1: Build the site (generate recipes.js from markdown)
FROM node:20-alpine AS builder

WORKDIR /build

# Copy recipe source files and build script
COPY recipes/ ./recipes/
COPY scripts/build-website.js ./scripts/
COPY website/ ./website/

# Run the build script to generate recipes.js
RUN node scripts/build-website.js

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy the built static files
COPY --from=builder /build/website/ /usr/share/nginx/html/

# Custom nginx config for SPA-style routing
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    gzip on; \
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml; \
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ { \
        expires 1d; \
        add_header Cache-Control "public, immutable"; \
    } \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /health { \
        access_log off; \
        return 200 "healthy\n"; \
        add_header Content-Type text/plain; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

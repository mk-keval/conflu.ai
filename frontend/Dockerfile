# Stage 1 — dev: Hot-reload Vite dev server
FROM node:20-alpine AS dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

COPY . .

EXPOSE 5173

# Stage 2 — builder: Build frontend assets
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

COPY . .
RUN npm run build

# Stage 3 — runtime: Nginx unprivileged with brotli
FROM nginxinc/nginx-unprivileged:1.25-alpine-slim

USER nginx

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:80/"]

EXPOSE 80

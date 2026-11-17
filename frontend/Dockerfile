# Root context preserves ../../Assets imports relative to frontend/src.
FROM node:22.14.0-alpine3.21 AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY Assets /app/Assets
# No .env is copied; the browser uses its own origin for /api.
RUN ./node_modules/.bin/tsc --noEmit -p tsconfig.json && npm run build
FROM nginxinc/nginx-unprivileged:1.28.0-alpine
COPY frontend/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 8080

# syntax=docker/dockerfile:1.7
# ---------- dependencies ----------
FROM node:22-alpine AS deps
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---------- dev (hot reload) ----------
FROM deps AS dev
ENV NODE_ENV=development
COPY --chown=node:node . .
EXPOSE 5173
HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=5 \
  CMD wget -qO- http://127.0.0.1:5173/ >/dev/null 2>&1 || exit 1
CMD ["npm", "run", "dev"]

# ---------- build ----------
FROM deps AS build
ENV NODE_ENV=production
COPY --chown=node:node . .
RUN npm run build

# ---------- production (static, non-root nginx on 8080) ----------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null 2>&1 || exit 1

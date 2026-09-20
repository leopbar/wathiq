# syntax=docker/dockerfile:1.7
# Official Playwright image: browsers and system libraries are already installed.
FROM mcr.microsoft.com/playwright:v1.63.0-noble
WORKDIR /e2e
ENV CI=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Playwright writes traces and the HTML report as it runs. Create those folders owned by the
# non-root user before the report volume is mounted, so Docker copies this ownership onto it.
RUN mkdir -p /e2e/test-results /e2e/playwright-report && chown -R pwuser:pwuser /e2e
USER pwuser
CMD ["npx", "playwright", "test"]

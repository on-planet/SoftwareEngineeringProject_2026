# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY repo/web/package*.json ./
RUN npm ci
COPY repo/web ./
ENV API_PROXY_TARGET=http://api:8000
RUN npm run build

# Production stage
FROM node:18-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV API_PROXY_TARGET=http://api:8000

COPY --from=builder /app/package*.json ./
RUN npm ci --production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./

EXPOSE 3000

CMD ["npm", "start"]

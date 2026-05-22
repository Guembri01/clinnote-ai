# ClinNote AI — Frontend Dockerfile
# Multi-stage build: build with Node, serve with nginx

# --- Build Stage ---
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./
RUN npm install

# Copy source
COPY . .

# Build for production
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_WS_BASE_URL=ws://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL

RUN npm run build

# --- Production Stage ---
FROM nginx:1.25-alpine AS production

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:80/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

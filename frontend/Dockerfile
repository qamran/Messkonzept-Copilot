# Frontend image for local Compose only (MKC-8); Vercel builds the deployed frontend.
# Vite inlines VITE_* values at build time, so they are build arguments.
# Base images are pinned by their multi-arch index digest.

# --- build: install the locked packages and build dist/
FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS build

WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
ARG VITE_CLERK_PUBLISHABLE_KEY=""
ARG VITE_API_URL="http://127.0.0.1:8000"
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY} \
    VITE_API_URL=${VITE_API_URL}
RUN npm run build

# --- serve: static files from an unprivileged nginx on port 8080
FROM nginxinc/nginx-unprivileged:1.30-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03 AS serve

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]

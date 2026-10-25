FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY app.conf /etc/nginx/chesso-app.conf
# The official image runs /docker-entrypoint.d/*.sh before starting nginx.
COPY certs.sh /docker-entrypoint.d/05-chesso-certs.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443

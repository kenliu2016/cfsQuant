# 第一阶段：构建前端
# 第一阶段：构建前端应用
FROM node:18-alpine AS build

# 设置构建参数，用于在构建时传入后端API地址
ARG VITE_API_BASE_URL=http://localhost:8000

# 设置环境变量，用于构建过程
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# 设置工作目录
WORKDIR /app/frontend

# 优化npm配置
RUN npm config set cache /tmp/npm-cache --global

# 复制package.json和package-lock.json
COPY package*.json ./

# 安装依赖（使用npm ci确保依赖版本与lock文件一致）
RUN npm ci --no-audit

# 复制项目代码
COPY . .

# 构建生产版本
RUN npm run build

# 第二阶段：使用Nginx服务静态文件
FROM nginx:1.25-alpine

# 设置时区
ARG TZ=Asia/Shanghai
ENV TZ=${TZ}

# 设置环境变量，默认值可以在运行时覆盖
ENV API_BASE_URL=http://localhost:8000

# 安装curl用于健康检查
RUN apk --no-cache add curl

# 复制构建产物到Nginx的静态文件目录
COPY --from=build /app/frontend/dist /usr/share/nginx/html

# 复制自定义Nginx配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 添加优化的Nginx全局配置
RUN echo 'worker_processes auto;' > /etc/nginx/nginx.conf && \
    echo 'events {' >> /etc/nginx/nginx.conf && \
    echo '    worker_connections 1024;' >> /etc/nginx/nginx.conf && \
    echo '}' >> /etc/nginx/nginx.conf && \
    echo 'http {' >> /etc/nginx/nginx.conf && \
    echo '    include /etc/nginx/mime.types;' >> /etc/nginx/nginx.conf && \
    echo '    default_type application/octet-stream;' >> /etc/nginx/nginx.conf && \
    echo '    sendfile on;' >> /etc/nginx/nginx.conf && \
    echo '    tcp_nopush on;' >> /etc/nginx/nginx.conf && \
    echo '    tcp_nodelay on;' >> /etc/nginx/nginx.conf && \
    echo '    keepalive_timeout 65;' >> /etc/nginx/nginx.conf && \
    echo '    gzip on;' >> /etc/nginx/nginx.conf && \
    echo '    gzip_disable "MSIE [1-6].(?!.*SV1)";' >> /etc/nginx/nginx.conf && \
    echo '    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;' >> /etc/nginx/nginx.conf && \
    echo '    include /etc/nginx/conf.d/*.conf;' >> /etc/nginx/nginx.conf && \
    echo '}' >> /etc/nginx/nginx.conf

# 复制替换API地址的脚本到容器中
COPY replace_api_url.sh /docker-entrypoint.d/
RUN chmod +x /docker-entrypoint.d/replace_api_url.sh

# 创建健康检查脚本
RUN echo '#!/bin/sh' > /healthcheck.sh && \
    echo 'curl -sf http://localhost || exit 1' >> /healthcheck.sh && \
    chmod +x /healthcheck.sh

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD ["/healthcheck.sh"]

# 暴露端口
EXPOSE 80

# Nginx默认的入口点会执行/docker-entrypoint.d/下的脚本
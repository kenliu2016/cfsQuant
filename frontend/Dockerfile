# 第一阶段：构建前端
FROM node:18-alpine AS build

# 设置构建参数，用于在构建时传入后端API地址
ARG VITE_API_BASE_URL

# 设置工作目录
WORKDIR /app/frontend

# 复制package.json和package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制项目代码
COPY . .

# 构建生产版本
RUN npm run build

# 第二阶段：使用Nginx服务静态文件
FROM nginx:1.25-alpine

# 设置环境变量，默认值可以在运行时覆盖
ENV VITE_API_BASE_URL=http://localhost:8000

# 复制构建产物到Nginx的静态文件目录
COPY --from=build /app/frontend/dist /usr/share/nginx/html

# 创建一个脚本，用于在Nginx启动前替换index.html中的API地址
RUN echo "#!/bin/sh\n\n# 替换静态文件中的API地址占位符\nfor file in $(find /usr/share/nginx/html -type f -name '*.js' -o -name '*.html' -o -name '*.css'); do\n  sed -i 's|http://localhost:8000|'"$VITE_API_BASE_URL"'|g' "$file"\ndone\n\n# 启动Nginx\nexec nginx -g 'daemon off;'" > /docker-entrypoint.d/replace_api_url.sh && \
    chmod +x /docker-entrypoint.d/replace_api_url.sh

# 暴露端口
EXPOSE 80

# Nginx默认的入口点会执行/docker-entrypoint.d/下的脚本
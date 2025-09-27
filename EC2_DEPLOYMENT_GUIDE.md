# EC2部署指南

## 系统要求
- AWS EC2实例（Ubuntu 20.04或CentOS 7/8）
- 至少2GB RAM，2个vCPU
- 至少10GB可用磁盘空间
- 安全组已开放端口：80（HTTP）、8000（后端API）

## 环境准备

### 1. 连接到EC2实例
使用SSH连接到您的EC2实例：

```bash
ssh -i "your-key.pem" ec2-user@13.213.2.53
```

### 2. 安装Docker和Docker Compose

#### Ubuntu系统
```bash
# 更新软件包列表
sudo apt-get update

# 安装必要的依赖
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

# 添加Docker的GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

# 添加Docker仓库
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

# 安装Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 将当前用户添加到docker组
sudo usermod -aG docker $USER
```

#### CentOS系统
```bash
# 安装Docker
sudo yum install -y yum-utils
sudo yum-config-manager \
    --add-repo \
    https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io

sudo systemctl start docker
sudo systemctl enable docker

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 将当前用户添加到docker组
sudo usermod -aG docker $USER
```

### 3. 安装Git
```bash
# Ubuntu
sudo apt-get install -y git

# CentOS
sudo yum install -y git
```

## 应用部署

### 1. 克隆代码仓库
```bash
# 替换为您的代码仓库地址
git clone https://github.com/your-username/cfsQuant.git
cd cfsQuant
```

### 2. 配置环境变量
编辑`.env`文件，确保包含以下配置：

```bash
# PostgreSQL配置 - 连接到EC1上的PostgreSQL（内网地址）
PGHOST=172.31.24.87  # EC1内网地址
PGPORT=5432
PGDATABASE=quant
PGUSER=cfs
PGPASSWORD=Cc563479,.

# Redis配置
# Redis服务在EC2上（当前部署服务器）
REDIS_HOST=172.31.25.234  # EC2内网地址
REDIS_PORT=6379
REDIS_DB=0
# Redis密码配置
REDIS_PASSWORD=Cc563479,.  # Redis密码

# 全局环境配置
TZ=Asia/Shanghai

# 后端服务配置
WORKERS_COUNT=2
LOG_LEVEL=INFO

# 前端服务配置
API_BASE_URL=http://backend:8000
VITE_API_BASE_URL=http://backend:8000
```

### 3. 创建并启动Docker服务
使用生产环境配置启动所有服务：

```bash
# 使用专门的生产环境配置文件启动服务
docker-compose -f docker-compose.prod.yml up -d --build
```

## 服务管理

### 查看服务状态
```bash
docker-compose -f docker-compose.prod.yml ps
```

### 查看服务日志
```bash
# 查看所有服务日志
docker-compose -f docker-compose.prod.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs backend
```

### 停止服务
```bash
docker-compose -f docker-compose.prod.yml down
```

### 重启服务
```bash
docker-compose -f docker-compose.prod.yml restart
```

## 验证服务

### 1. 验证前端服务
打开浏览器访问EC2的公网IP：
```
http://13.213.2.53
```

### 2. 验证后端API
```bash
# 在EC2实例上执行
curl http://localhost:8000/api/health

# 从本地机器执行
curl http://13.213.2.53:8000/api/health
```

预期响应：
```json
{"status":"ok"}
```

## 故障排除

### 1. 连接数据库失败
- 确保EC1的安全组允许从EC2的内网IP访问5432端口
- 验证`.env`文件中的数据库连接信息是否正确
- 检查数据库服务是否正常运行

### 2. 连接Redis失败
- 确保Redis配置正确，包括主机地址、端口和密码
- 验证Redis服务是否正常运行
- 检查防火墙设置

### 3. 服务启动失败
查看详细日志以确定问题：
```bash
docker-compose -f docker-compose.prod.yml logs --tail=100 [service-name]
```

### 4. 前端无法连接后端API
- 检查Nginx配置
- 验证环境变量`API_BASE_URL`是否正确设置
- 查看前端容器日志

## 定期维护

### 1. 更新应用
```bash
git pull
docker-compose -f docker-compose.prod.yml up -d --build
```

### 2. 清理未使用的资源
```bash
docker system prune -a
```

## 安全建议
- 定期更新Docker镜像和依赖
- 考虑使用HTTPS（可以使用AWS ACM或Let's Encrypt）
- 限制直接访问后端API端口（8000），只允许从前端服务访问
- 定期备份数据库和重要数据
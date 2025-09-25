# 项目部署指南

本指南将帮助您将cfsQuant项目部署到云服务器上。项目采用Docker容器化部署，包含前端、后端和Celery服务，使用外部PostgreSQL数据库和Redis服务。

## 系统架构

- **前端**：基于React + TypeScript + Vite构建的单页应用
- **后端**：基于FastAPI的Python服务
- **任务队列**：Celery（基于外部Redis）
- **数据库**：外部PostgreSQL 14服务器
- **缓存**：外部Redis 7服务器

## 前置条件

在开始部署前，请确保您的云服务器满足以下要求：

- 操作系统：Ubuntu 20.04或更高版本
- CPU：至少2核
- 内存：至少4GB
- 存储：至少20GB可用空间
- 已安装Docker和Docker Compose
- 开放以下端口：80（HTTP）、8000（后端API）
- 可访问的外部PostgreSQL数据库服务器
- 可访问的外部Redis服务器

## 安装Docker和Docker Compose

如果您的服务器尚未安装Docker和Docker Compose，请按照以下步骤安装：

```bash
# 更新系统包
sudo apt-get update

sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 添加Docker官方GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 设置稳定版仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker引擎
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

## 部署步骤

### 1. 克隆项目代码

```bash
# 克隆项目代码到服务器
git clone <your-repository-url> cfsQuant
cd cfsQuant
```

### 2. 配置环境变量

由于项目使用外部PostgreSQL和Redis服务器，您需要设置相应的环境变量。有两种方式配置这些环境变量：

#### 方式一：使用.env文件

在项目根目录创建`.env`文件，并添加以下内容：

```bash
# PostgreSQL配置
PGHOST=your_postgresql_host
PGPORT=5432
PGDATABASE=quant
PGUSER=your_postgresql_username
PGPASSWORD=your_postgresql_password

# Redis配置
REDIS_HOST=your_redis_host
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password # 如果Redis设置了密码
```

#### 方式二：直接修改docker-compose.yml文件

您也可以直接在`docker-compose.yml`文件中修改环境变量的值，但推荐使用`.env`文件以便于管理和安全考虑。

#### 其他配置文件

- `backend/config/db_config.yaml`：数据库和Redis配置（环境变量会覆盖此文件中的配置）
- `docker-compose.yml`：容器编排配置

### 3. 构建和启动服务

使用Docker Compose构建和启动所有服务：

```bash
# 在项目根目录执行
docker-compose up -d --build
```

这条命令会：
- 构建前端和后端的Docker镜像
- 下载PostgreSQL和Redis的官方镜像
- 创建并启动所有服务容器
- 将数据卷挂载到容器中以持久化数据

### 4. 验证服务是否正常运行

```bash
# 检查所有服务的状态
docker-compose ps

# 查看后端服务日志
docker-compose logs -f backend

# 查看前端服务日志
docker-compose logs -f frontend
```

### 5. 数据库初始化（如需要）

如果是首次部署，可能需要初始化数据库表结构：

```bash
# 进入后端容器
docker-compose exec backend bash

# 运行数据库初始化脚本
python -m app.db.init
```

## 服务访问

部署完成后，您可以通过以下方式访问服务：

- **前端应用**：http://服务器IP地址 或 http://域名
- **后端API**：http://服务器IP地址:8000 或 http://域名:8000
- **API文档**：http://服务器IP地址:8000/docs 或 http://域名:8000/docs

## Celery服务说明

项目包含以下Celery服务：

- **celery_worker_tuning**：处理参数调优任务的工作节点
- **celery_worker_default**：处理默认队列任务的工作节点
- **celery_beat**：定时任务调度器（如果项目中有定时任务需求）

这些服务使用外部Redis服务器作为消息代理和结果后端。

## 数据持久化

由于数据库和Redis服务在外部服务器上，数据持久化由外部服务负责。项目本身不包含数据库和Redis的数据卷配置。

容器内的代码通过Docker挂载卷保持同步，便于开发和更新：
- `./backend/app:/app/backend/app`：后端代码挂载卷

## 监控和维护

### 查看容器日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
```

### 进入容器

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入数据库容器
docker-compose exec postgres psql -U cfs -d quant
```

### 更新服务

当代码更新时，使用以下命令重新构建和启动服务：

```bash
# 拉取最新代码
git pull

# 重新构建并启动服务
docker-compose up -d --build
```

## 环境变量配置

项目支持以下环境变量覆盖默认配置，包括数据库连接参数和前端后端接口地址配置：

### PostgreSQL相关（外部服务器）
- `PGHOST`：PostgreSQL主机地址（必须配置）
- `PGPORT`：PostgreSQL端口（默认为5432）
- `PGDATABASE`：数据库名称（默认为quant）
- `PGUSER`：数据库用户名（必须配置）
- `PGPASSWORD`：数据库密码（必须配置）

### Redis相关（外部服务器，用于缓存和Celery）
- `REDIS_HOST`：Redis主机地址（必须配置）
- `REDIS_PORT`：Redis端口（默认为6379）
- `REDIS_DB`：Redis数据库编号（默认为0）
- `REDIS_PASSWORD`：Redis密码（如果Redis服务器设置了密码）

### 前端后端接口地址配置

当前端和后端部署在不同服务器上时，需要配置前端应用的后端API地址。有以下几种配置方式：

1. **在构建时配置**
   
   在构建前端Docker镜像时，可以通过`--build-arg`参数指定后端API地址：
   
   ```bash
   docker build -t frontend:latest --build-arg VITE_API_BASE_URL=http://backend-server:8000 .
   ```

2. **在运行时配置**
   
   在运行前端Docker容器时，可以通过`-e`参数覆盖后端API地址：
   
   ```bash
   docker run -d -p 80:80 -e VITE_API_BASE_URL=http://backend-server:8000 frontend:latest
   ```

3. **使用docker-compose.yml配置**
   
   在docker-compose.yml文件中，可以通过environment字段设置环境变量：
   
   ```yaml
   frontend:
     build: ./frontend
     ports:
       - "80:80"
     environment:
       - VITE_API_BASE_URL=http://backend-server:8000
   ```

> **注意**：配置的后端API地址必须是前端服务器可以访问到的地址，通常是后端服务器的公网IP或域名，以及对应的端口号。

## 常见问题解决

### 1. 服务启动失败

检查Docker日志以获取详细错误信息：

```bash
docker-compose logs -f
```

### 2. 外部数据库连接问题

确保外部PostgreSQL服务器可访问且环境变量配置正确。可以通过以下命令验证数据库连接（请先替换为您的实际配置）：

```bash
docker-compose exec backend python -c "import psycopg2; conn = psycopg2.connect(host='your_postgresql_host', port=5432, dbname='quant', user='your_username', password='your_password'); print('Connection successful!'); conn.close()"
```

### 3. Redis连接问题

确保外部Redis服务器可访问且环境变量配置正确。可以通过以下命令验证Redis连接（请先替换为您的实际配置）：

```bash
docker-compose exec backend python -c "import redis; r = redis.Redis(host='your_redis_host', port=6379, db=0, password='your_redis_password' if 'your_redis_password' else None); r.ping(); print('Connection successful!')"
```

### 4. 前端无法访问后端API

检查网络配置和CORS设置，确保前端可以跨域访问后端API。

### 5. Celery任务执行问题

如果Celery任务执行失败，请检查Redis连接和任务日志：

```bash
docker-compose logs -f celery_worker_tuning
```

## 性能优化建议

1. **调整资源限制**：根据服务器配置和业务需求，调整Docker容器的CPU和内存限制。
2. **启用HTTPS**：在生产环境中，建议使用SSL证书配置HTTPS访问。
3. **配置反向代理**：使用Nginx或Apache作为反向代理，优化静态资源缓存和请求分发。
4. **定期备份数据**：配置定期数据库备份策略，确保数据安全。

## 高级部署选项

### 使用CI/CD自动化部署

对于生产环境，建议配置CI/CD流水线实现自动化部署。您可以使用GitHub Actions、GitLab CI/CD或Jenkins等工具。

### 水平扩展

当流量增加时，可以通过增加容器实例数量实现水平扩展。对于有状态服务（如PostgreSQL），需要考虑集群配置。
# cfsQuant 两套Backend服务部署方案

## 方案概述

为了解决参数调优任务对主Backend服务性能的影响，本方案在同一EC2实例上部署两套独立的Backend服务：

1. **主Backend服务** (backend_primary)：负责处理所有API请求，不执行Celery任务
2. **第二套Backend服务** (backend_secondary)：专门用于执行参数调优任务
3. **参数调优Celery Worker** (celery_worker_tuning)：连接到第二套Backend服务，执行参数调优任务
4. **前端服务** (frontend)：连接到主Backend服务

这样可以确保参数调优任务在独立的服务实例中执行，不会影响主服务的性能和响应速度。

## 目录结构

```
├── docker-compose.two_backends.yml  # 两套Backend服务的Docker Compose配置
├── start_two_backends.sh           # 启动和管理脚本
├── backend/
│   ├── app/celery_config.py        # 已修改的Celery配置文件
│   ├── Dockerfile                  # 后端Docker构建文件
│   └── ...
└── frontend/
    └── ...
```

## 主要修改内容

### 1. Docker Compose配置

创建了`docker-compose.two_backends.yml`文件，包含：
- 定义了两个独立的Backend服务容器
- 前端服务连接到主Backend服务
- 参数调优Celery Worker连接到第二套Backend服务
- 增加了第二套Backend服务和Celery Worker的资源限制
- 通过环境变量`IS_SECONDARY_INSTANCE=true`标识第二套实例

### 2. Celery配置修改

修改了`backend/app/celery_config.py`文件，增加：
- 基于环境变量`IS_SECONDARY_INSTANCE`的条件配置
- 第二套实例使用不同的Celery应用名称(`cfsQuant_secondary`)以避免冲突
- 根据实例类型加载不同的服务模块

### 3. 启动和管理脚本

创建了`start_two_backends.sh`脚本，提供：
- 服务启动、停止、状态查看功能
- 环境变量检查
- Docker安装检查
- 参数调优任务日志查看功能

## 使用方法

### 前提条件

1. 已安装Docker和docker-compose
2. 已设置必要的环境变量（可在.env文件中设置或直接导出）：
   - PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD (PostgreSQL连接信息)
   - REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD (Redis连接信息)

### 启动服务

```bash
./start_two_backends.sh start
```

启动后，系统会：
- 构建和启动两套Backend服务、Celery Worker和前端服务
- 主Backend服务监听8000端口
- 前端服务监听80端口

### 停止服务

```bash
./start_two_backends.sh stop
```

### 查看服务状态

```bash
./start_two_backends.sh status
```

### 查看参数调优任务日志

```bash
./start_two_backends.sh logs
```

## 性能优化建议

1. 根据EC2实例的CPU和内存配置，调整`docker-compose.two_backends.yml`中的资源限制参数
2. 对于大型参数调优任务，可以进一步增加`celery_worker_tuning`服务的CPU和内存限制
3. 考虑设置任务超时和重试策略，避免长时间运行的任务占用资源

## 注意事项

1. 两套Backend服务共享同一个PostgreSQL数据库和Redis服务
2. 确保EC2实例有足够的资源运行两套Backend服务
3. 如需修改服务配置，请直接编辑`docker-compose.two_backends.yml`文件
4. 本方案不会影响现有的业务逻辑，只是将任务执行环境分离

## 故障排查

1. 如果服务启动失败，检查Docker日志获取详细错误信息：
   ```bash
docker logs quant-backend-primary
   ```

2. 如果参数调优任务执行异常，查看Celery Worker日志：
   ```bash
./start_two_backends.sh logs
   ```

3. 检查环境变量设置是否正确：
   ```bash
env | grep -E "PG|REDIS"
   ```
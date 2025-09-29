#!/bin/bash

# 启动脚本 - 用于管理两套backend服务的部署

# 设置颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查Docker是否已安装
check_docker() {
    if ! command -v docker &> /dev/null;
    then
        echo -e "${RED}错误: Docker未安装。请先安装Docker。${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null;
    then
        echo -e "${RED}错误: docker-compose未安装。请先安装docker-compose。${NC}"
        exit 1
    fi
}

# 检查环境变量
check_env() {
    # 检查必要的环境变量是否已设置
    local required_vars=("PGHOST" "PGPORT" "PGDATABASE" "PGUSER" "PGPASSWORD" "REDIS_HOST" "REDIS_PORT" "REDIS_DB" "REDIS_PASSWORD")
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo -e "${YELLOW}警告: 环境变量 $var 未设置。请在.env文件中设置或直接导出。${NC}"
        fi
    done
}

# 启动服务
start_services() {
    echo -e "${BLUE}正在启动两套backend服务...${NC}"
    docker-compose -f docker-compose.two_backends.yml up -d --build
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}服务启动成功！${NC}"
        echo -e "${GREEN}主Backend服务: http://localhost:8000${NC}"
        echo -e "${GREEN}前端服务: http://localhost${NC}"
        echo -e "${GREEN}参数调优任务将在第二套Backend服务中执行。${NC}"
    else
        echo -e "${RED}服务启动失败，请检查错误日志。${NC}"
    fi
}

# 停止服务
stop_services() {
    echo -e "${BLUE}正在停止两套backend服务...${NC}"
    docker-compose -f docker-compose.two_backends.yml down
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}服务停止成功！${NC}"
    else
        echo -e "${RED}服务停止失败，请检查错误日志。${NC}"
    fi
}

# 查看服务状态
status_services() {
    echo -e "${BLUE}查看服务状态...${NC}"
    docker-compose -f docker-compose.two_backends.yml ps
    echo -e "\n${BLUE}查看容器日志...${NC}"
    docker-compose -f docker-compose.two_backends.yml logs --tail=10
}

# 查看参数调优任务日志
view_tuning_logs() {
    echo -e "${BLUE}查看参数调优任务日志...${NC}"
    docker logs -f quant-celery-worker-tuning
}

# 帮助信息
show_help() {
    echo -e "${GREEN}cfsQuant 两套Backend服务管理脚本${NC}"
    echo -e "用法: $0 [start|stop|status|logs|help]"
    echo -e "\n命令:\"
    echo -e "  start    启动两套backend服务"
    echo -e "  stop     停止两套backend服务"
    echo -e "  status   查看服务状态"
    echo -e "  logs     查看参数调优任务日志"
    echo -e "  help     显示帮助信息"
    echo -e "\n说明:"
    echo -e "  此脚本用于管理两套backend服务的部署，确保参数调优任务在第二套服务中执行。"
    echo -e "  主服务(backend_primary)负责处理API请求，第二套服务(backend_secondary)负责处理Celery任务。"
}

# 主函数
main() {
    check_docker
    check_env
    
    case "$1" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        status)
            status_services
            ;;
        logs)
            view_tuning_logs
            ;;
        help)
            show_help
            ;;
        *)
            echo -e "${RED}错误: 无效的命令。请使用 $0 help 查看可用命令。${NC}"
            exit 1
            ;;
    esac
}

# 调用主函数
main "$@"
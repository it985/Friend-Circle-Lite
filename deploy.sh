#!/bin/bash

# 获取当前脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检查脚本权限
if [ ! -x "$0" ]; then
    echo "设置脚本执行权限..."
    chmod +x "$0"
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3，请先安装Python 3"
    exit 1
fi

# 检查依赖
if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "错误: 未找到requirements.txt文件"
    exit 1
fi

# 安装依赖
echo "安装Python依赖..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    echo "错误: 依赖安装失败"
    exit 1
fi

# 检查配置文件
if [ ! -f "$SCRIPT_DIR/conf.yaml" ]; then
    echo "错误: 未找到conf.yaml配置文件"
    exit 1
fi

echo "===================================="

# 定义 API 服务的启动命令
API_COMMAND="python3 $SCRIPT_DIR/server.py"

# 检查是否已有API服务在运行
API_PID=$(pgrep -f "python3.*server.py")
if [ ! -z "$API_PID" ]; then
    echo "发现已有API服务在运行，进程号: $API_PID"
    read -p "是否停止现有服务? (y/n): " stop_existing
    if [ "$stop_existing" = "y" ]; then
        kill -9 $API_PID
        echo "已停止现有服务"
        sleep 2
    else
        echo "保持现有服务运行"
    fi
fi

# 后台运行服务端，将数据映射到API
echo "****正在启动API服务****"
nohup $API_COMMAND > "$SCRIPT_DIR/api.log" 2>&1 &
API_PID=$!
sleep 5  # 等待API服务启动

# 检查服务是否成功启动
if kill -0 $API_PID 2>/dev/null; then
    echo "API 服务已启动：http://localhost:1223"
    echo "API 服务进程号：$API_PID"
    echo "API 服务日志：$SCRIPT_DIR/api.log"
    echo "API 服务关闭命令：kill -9 $API_PID"
    echo "文档地址：https://blog.liushen.fun/posts/4dc716ec/"
else
    echo "错误: API服务启动失败，请检查日志: $SCRIPT_DIR/api.log"
    exit 1
fi

echo "===================================="

# 用户选择是否执行爬取
read -p "选择操作：0 - 退出, 1 - 执行一次爬取: " USER_CHOICE

if [ "$USER_CHOICE" -eq 1 ]; then
    echo "****正在执行一次爬取****"
    python3 "$SCRIPT_DIR/run.py"
    if [ $? -eq 0 ]; then
        echo "****爬取成功****"
    else
        echo "****爬取失败，请检查日志****"
    fi
else
    echo "退出选项被选择，掰掰！"
fi

echo "===================================="
echo "定时抓取的部分请自行设置，如果有宝塔等面板可以按照说明直接添加"
echo "===================================="

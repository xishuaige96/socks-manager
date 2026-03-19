#!/bin/bash

# 名为check_live的screen会话名称
SCREEN_NAME="check_live"
PYTHON_SCRIPT="/root/server/socks-manger/check_live.py"

# 发送Ctrl+C命令并关闭现有的check_live会话
screen -S $SCREEN_NAME -p 0 -X stuff "^C"
screen -S $SCREEN_NAME -X quit

# 新建check_live会话并运行Python脚本
screen -dmS $SCREEN_NAME
screen -S $SCREEN_NAME -p 0 -X stuff "python3 $PYTHON_SCRIPT\n"

echo "Script restarted in screen session: $SCREEN_NAME"

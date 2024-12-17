#!/bin/bash

scriptFilename="setup_server.sh"
scriptFilename2="setup_server2.sh"
zipname="SocksAB.zip"
unzipname="SocksAB"
password=$1

cd ~
echo $password | sudo -S rm -rf $unzipname
echo $password | sudo -S rm $zipname
echo $password | sudo -S rm scriptFilename
echo $password | sudo -S rm scriptFilename2

screen -X -S jiedian quit

# 以下是删除所有Alice窗口
# 获取所有包含Alice的screen会话
sessions=$(screen -ls | awk '/Alice/ {print $1}')
# 检查是否有匹配的会话
if [ -n "$sessions" ]; then
    # 遍历并关闭每个匹配的会话
    for session in $sessions; do
        # 提取会话的ID部分
        session_id=${session%%.*}
        echo "Killing screen session: $session_id"
        screen -X -S $session_id quit
    done
else
    echo "No screen sessions starting with 'Alice' found."
fi

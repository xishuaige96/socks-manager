#!/bin/bash

MAX_RETRY=3  # 设置最大重试次数

zipname="program_package.zip"
unzipname="program_package"
password=$1
zhongkong_ip=$2


# 定义函数用于执行apt install命令
apt_install() {
    echo $password | sudo -S apt update
    echo $password | sudo -S apt install -y screen python3-pip unzip
}
# 定义函数用于执行pip install命令
pip_install() {
    pip install requests psutil
}

# 重置重试计数器
retry_count=0
while true; do
    apt_install  # 执行apt install命令

    # 检查命令的返回状态码
    if [ $? -eq 0 ]; then
        echo "apt install成功！"
        break  # 如果apt install成功，则跳出循环
    else
        # 如果apt install失败，则判断是否达到最大重试次数
        if [ $retry_count -lt $MAX_RETRY ]; then
            echo "apt install失败，进行重试..."
            retry_count=$((retry_count + 1))
        else
            echo "重试次数已达到最大限制，无法执行apt install。"
            exit 1  # 如果重试次数用尽，退出脚本并返回错误状态码
        fi
    fi
done

# 重置重试计数器
retry_count=0
while true; do
    pip_install  # 执行pip install命令

    # 检查命令的返回状态码
    if [ $? -eq 0 ]; then
        echo "pip install成功！"
        break  # 如果pip install成功，则跳出循环
    else
        # 如果pip install失败，则判断是否达到最大重试次数
        if [ $retry_count -lt $MAX_RETRY ]; then
            echo "pip install失败，进行重试..."
            retry_count=$((retry_count + 1))
        else
            echo "重试次数已达到最大限制，无法执行pip install。"
            exit 1  # 如果重试次数用尽，退出脚本并返回错误状态码
        fi
    fi
done


echo $password | sudo -S ufw disable
echo $password | sudo -S systemctl disable ufw

cd ~
echo $password | sudo -S rm -rf $unzipname

# 以下是删除所有proxyProgram窗口
# 获取所有包含proxyProgram的screen会话
sessions=$(screen -ls | awk '/proxyProgram/ {print $1}')
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
    echo "No screen sessions starting with 'proxyProgram' found."
fi

unzip $zipname
cd $unzipname
chmod +x main

screen -X -S jiedian quit
screen -dmS jiedian
screen -S jiedian -X stuff "python3 jiedian.py $2\n"


exit 0  # 如果所有命令成功执行，退出脚本并返回成功状态码

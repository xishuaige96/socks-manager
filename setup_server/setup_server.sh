#!/bin/bash

MAX_RETRY=3  # 设置最大重试次数

zipname="SocksAB.zip"
unzipname="SocksAB"
password=$1


# 定义函数用于执行apt install命令
apt_install() {
    echo $password | sudo -S apt update
    echo $password | sudo -S apt install -y qtbase5-dev libbotan-2-dev screen python3-pip
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
# if [ -d $unzipname ]; then # 若先前已有root用户创建的$unzipname文件夹，当前用户无法删除，则后续unzip时会产生询问
#     echo "无法删除文件$unzipname"
#     exit 2
# fi
unzip $zipname
cd ./$unzipname/bin
chmod +x Socks-Alice Socks-Bob

screen -X -S jiedian quit
screen -dmS jiedian
screen -S jiedian -X stuff "python3 jiedian.py\n"


exit 0  # 如果所有命令成功执行，退出脚本并返回成功状态码

#!/bin/bash

password=$1

# 关闭1000以下的端口
echo $password | sudo -S iptables -A INPUT -p tcp --dport 1:999 -j DROP

# 修改SSH端口为2222
echo $password | sudo -S sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

# 重启SSH服务
echo $password | sudo -S service ssh restart

# 保存iptables规则
echo $password | sudo -S mkdir /etc/iptables
echo $password | sudo -S iptables-save > /etc/iptables/rules.v4

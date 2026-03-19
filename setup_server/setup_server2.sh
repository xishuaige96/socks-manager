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

# 提升文件描述符限制
echo "Increasing file descriptor limits..."
echo '* soft nofile 65535' | sudo tee -a /etc/security/limits.conf
echo '* hard nofile 65535' | sudo tee -a /etc/security/limits.conf
ulimit -n 65535

# 调整sysctl参数
echo "Adjusting sysctl parameters..."
sudo sysctl -w net.core.somaxconn=65535
sudo sysctl -w net.core.netdev_max_backlog=65535
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=65535
sudo sysctl -w net.ipv4.tcp_max_tw_buckets=2000000
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
sudo sysctl -w net.ipv4.tcp_tw_reuse=1

# 调整TCP缓冲区大小
echo "Adjusting TCP buffer sizes..."
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"

# 禁用TCP窗口缩放
echo "Disabling TCP window scaling..."
sudo sysctl -w net.ipv4.tcp_window_scaling=0

# 优化TCP Keepalive参数
echo "Optimizing TCP keepalive parameters..."
sudo sysctl -w net.ipv4.tcp_keepalive_time=600
sudo sysctl -w net.ipv4.tcp_keepalive_intvl=60
sudo sysctl -w net.ipv4.tcp_keepalive_probes=5

# 调整网络队列长度
echo "Adjusting network queue length..."
sudo sysctl -w net.core.netdev_max_backlog=5000

# 获取网络接口名称
NET_INTERFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -v "lo" | head -n 1)
echo "Using network interface: $NET_INTERFACE"

# 调整网络接口，启用多队列
echo "Enabling multi-queue on network interface..."
if [ -z "$NET_INTERFACE" ]; then
  echo "No valid network interface found. Skipping multi-queue configuration."
else
  sudo ethtool -L $NET_INTERFACE combined 4 || echo "Failed to set multi-queue parameters for $NET_INTERFACE"
fi

# 启用网卡的中断平衡
echo "Enabling IRQ balance..."
sudo apt-get install -y irqbalance
sudo systemctl enable irqbalance
sudo systemctl start irqbalance

# 优化网络栈，选择TCP BBR算法
echo "Optimizing network stack with TCP BBR..."
echo "net.core.default_qdisc=fq" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" | sudo tee -a /etc/sysctl.conf

# 重新加载sysctl配置
echo "Reloading sysctl configuration..."
sudo sysctl -p

echo "VPN node performance optimization complete."

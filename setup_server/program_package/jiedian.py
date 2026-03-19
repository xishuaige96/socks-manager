import time
import requests
import psutil
import socket
import sys

HEARTBEAT_INTERVAL = 30
MASTER_SERVER_URL = 'http://127.0.0.1:3000/heartbeat'
# MASTER_SERVER_URL = 'http://127.0.0.1:80/heartbeat'
# port = 1082


def check_service(port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(('127.0.0.1', port))
            return 1
        except ConnectionRefusedError:
            return 0


def get_status():
    # 获取CPU占用率
    cpu_percent = psutil.cpu_percent(interval=1)

    # 获取内存使用量和内存使用率
    memory = psutil.virtual_memory()
    memory_usage = memory.used / (1024 * 1024)  # 转换为MB单位
    memory_percent = memory.percent

    # 获取网络上行和下行速度
    network = psutil.net_io_counters()
    network_upload = network.bytes_sent
    network_download = network.bytes_recv

    # 等待一段时间
    time.sleep(1)

    # 再次获取网络上行和下行速度
    network = psutil.net_io_counters()
    network_upload_speed = (network.bytes_sent - network_upload) / 1024  # 转换为KB/s单位
    network_download_speed = (network.bytes_recv - network_download) / 1024  # 转换为KB/s单位

    # with open('../conf/bob_port.txt','r') as file:
    #     port=int(file.read())

    # live_flag = check_service(port)
    live_flag=1

    return cpu_percent, memory_usage, memory_percent, network_upload_speed, network_download_speed, live_flag


if __name__ == '__main__':
    master_server_ip = sys.argv[1]
    MASTER_SERVER_URL=f'http://{master_server_ip}:3000/heartbeat'

    while True:
        cpu_percent, memory_usage, memory_percent, network_upload_speed, network_download_speed, live_flag = get_status()
        # Record the send time
        send_time = time.time()

        try:
        # Send the heartbeat request with the send time as a parameter
            requests.get(MASTER_SERVER_URL, params={'time': send_time, 'cpu_percent': cpu_percent,
                                                    'memory_usage': memory_usage, 'memory_percent': memory_percent,
                                                    'network_upload_speed': network_upload_speed,
                                                    'network_download_speed': network_download_speed,
                                                    'live_flag': live_flag}, timeout=10)
        except Exception as e:
            print(f"An error occurred: {e}")

        time.sleep(HEARTBEAT_INTERVAL)

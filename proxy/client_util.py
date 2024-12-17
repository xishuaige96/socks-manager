import requests
import random
import json
import os

proxy_center_server_url = 'http://127.0.0.1:5001/'

timeout = 3  # 超时时间

retry = 2  # 重试次数


def gen_authcode() -> str:
    """
    生成身份认证码
    """
    return '123456'


def request_for_server_list():
    """
    请求超时的处理，即向代理中心请求新的列表
    """
    response = requests.post(proxy_center_server_url +
                             'getServerList', json={'authcode': gen_authcode()})
    print(response.status_code, response.content)

    if response.status_code == 403:
        raise Exception(f'拒绝服务：{response.json()["message"]}')

    data = response.json()
    if not os.path.exists('cache'):
        os.makedirs('cache')
    with open('./cache/proxy_server_list.json', 'w') as f:
        json.dump(data, f)


def get_server() -> str:
    """
    随机从本地缓存的转发服务器列表中获取一个。返回一个ip地址
    """
    if not os.path.exists('./cache/proxy_server_list.json'):
        print('本地无缓存，请求节点列表服务器')
        request_for_server_list()
        print('节点列表获取成功')
    with open('./cache/proxy_server_list.json', 'r') as f:
        return random.choice(json.load(f))


def send(method, json=None, headers=None):
    """
    requests.request的一个包装
    :param method: 请求方法，可以为 'POST','GET'
    :param json: 负载
    :param headers: 请求头
    :return: 返回response
    """
    hasRegetServerList = False
    serverIp = get_server()
    for i in range(1, retry + 2):
        try:
            # print('serverIp=',serverIp)
            response = requests.request(
                method, 'http://' + serverIp + ':5000/', headers=headers, data=json, timeout=timeout)
            return response
        except requests.exceptions.ConnectionError or requests.exceptions.Timeout:
            if hasRegetServerList:
                raise Exception('服务器不可用')
            print(f'第{i}次请求超时')
            if i == retry:
                print(f'重新获取服务器列表')
                request_for_server_list()
                hasRegetServerList = True
                serverIp = get_server()
                print('已重新获取服务器列表')


def _test():
    # request_for_server_list()
    print(send('POST', json={'hello': 'world'}))


if __name__ == '__main__':
    _test()

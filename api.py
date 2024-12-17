import hashlib
from datetime import datetime

import requests
from Crypto.Cipher import AES
import json
import base64

key_str = 'hitcs2020!123456'
key = key_str.encode()
subscription_data = [
    {
        "types": "动态随机",
        "name": "动态随机链路1",
        "mask": "单一伪装",
        "encryption": "chacha20",
        "targetType": 0,
        "target": "45.76.139.94",
        "linkLength": 2
    },
    {
        "types": "动态随机",
        "name": "动态随机链路2",
        "mask": "混合伪装",
        "encryption": "chacha20",
        "targetType": 1,
        "target": "日本",
        "linkLength": 2
    },
    {
        "types": "动态随机",
        "name": "动态随机链路2",
        "mask": "混合伪装",
        "encryption": "chacha20",
        "targetType": 1,
        "target": "国外",
        "linkLength": 3
    }
]


def encrypt(plaintext: str):
    # 创建一个cipher对象用于加密
    cipher = AES.new(key, AES.MODE_EAX)

    # 加密数据
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())

    # 我们需要保存nonce, tag和密文，以便我们可以解密它
    encrypted_data = {
        'nonce': base64.b64encode(cipher.nonce).decode('utf-8'),
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
        'tag': base64.b64encode(tag).decode('utf-8')
    }
    dict_str = json.dumps(encrypted_data).encode()
    encoded_str = base64.b64encode(dict_str).decode()
    return encoded_str


def encrypt_dynamic(data: dict):
    formatted_date = datetime.now().date().strftime("%Y%m%d")
    data_str = json.dumps(data)
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(data_str.encode())
    encrypted_data = {
        'nonce': base64.b64encode(cipher.nonce).decode('utf-8'),
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
        'tag': base64.b64encode(tag).decode('utf-8')
    }
    return encrypted_data


def decrypt_dynamic(data: dict):
    formatted_date = datetime.now().date().strftime("%Y%m%d")
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    nonce = base64.b64decode(data['nonce'])
    ciphertext = base64.b64decode(data['ciphertext'])
    tag = base64.b64decode(data['tag'])
    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    data = cipher.decrypt_and_verify(ciphertext, tag)
    data = json.loads(data.decode())
    return data


url = 'http://47.95.38.164:3000/'


# 添加ssh配置
def addSSHConfig(ip, port: int, username, password: str, node_name, servicer, bandwidth, country, city=""):
    data_json = {"ip": ip, "port": port, "username": username, "password": encrypt(password), "node_name": node_name,
                 "servicer": servicer, "bandwidth": bandwidth, "country": country, "city": city}
    response = requests.post(url + "addSshConfig", json=data_json)
    return response.json()


def setupServer(ip, bob_port=None, bob_password=None, bob_encrypt_method=None, should_random=True):
    data_json = {"ip": ip, "bob_port": bob_port, "bob_password": bob_password, "bob_encrypt_method": bob_encrypt_method,
                 "shouldRandom": should_random}
    response = requests.post(url + "setupServer", json=data_json)
    return response.json()


def createSubscription(subscriptionName, data=None):
    if data is None:
        data = subscription_data
    dic = {"subscriptionName": subscriptionName, "data": encrypt(json.dumps({"data": data}))}
    response = requests.post(url + "createSubscription", json=dic)
    return response.json()


def deleteSub(subscriptionName):
    data_json = {"subscriptionName": subscriptionName}
    response = requests.post(url + "deleteSubscription", json=data_json)
    return response.json()


def getLink(subscriptionName, linkMethodId: str, username):
    data_json = {"subscriptionName": subscriptionName, "linkMethodId": linkMethodId, "username": username}
    response = requests.post(url + "getlink", json=encrypt_dynamic(data_json))
    ret = response.json()
    return decrypt_dynamic(ret["data"])


def deleteLink(username):
    data_json = {"username": username}
    response = requests.post(url + "deleteLink", json=data_json)
    return response.json()


def server(user, addr):
    data_json = {"user": user, "addr": addr}
    response = requests.post(url + "server", json=data_json)
    print(response)
    return response.json()


def changePassword(username, old_password, new_password):
    old_password = hashlib.sha256(old_password.encode('utf-8')).hexdigest()
    new_password = hashlib.sha256(new_password.encode('utf-8')).hexdigest()
    data_json = {"username": username, "old_password": old_password, "new_password": new_password}
    response = requests.post(url + "/changepasswd", json=data_json)
    return response.json()


def __proccess():
    """
    部署服务器的流程、代码模板。

    tips:
    如果没有正常删除用户链路，则需要改userlist中的used-links-count为0或为空
    """
    a = addSSHConfig("43.139.114.50", 22, "ubuntu", "hitcs2023!", "国内节点50", "腾讯云", "10M", "中国", "广州")
    a = setupServer("43.139.114.50")
    a = createSubscription("subscription")
    a = deleteSub("subscription")
    a = getLink("订阅分组1", "1", "guoguo")
    print(a)


if __name__ == '__main__':
    # addSSHConfig("149.28.19.158", 22, "root", "3eG(seKn!?6#zbHn", "国外节点1", "vultr", "10M", "日本", "Tokyo")
    # addSSHConfig("167.179.113.210", 22, "root", "8zB%h},62y}[(mR?", "国外节点2", "vultr", "5M", "日本", "Tokyo")
    # addSSHConfig("202.182.100.184", 22, "root", "v+Y3},(yywsrjVjf", "国外节点3", "vultr", "3M", "日本", "Tokyo")
    # addSSHConfig("45.76.139.94", 22, "root", ")R2nmo6ys,NUHv@K", "国外节点4", "vultr", "10M", "美国", "Los Angeles")
    # addSSHConfig("45.77.166.154", 22, "root", "y[7LS7Thw6mSb.eC", "国外节点5", "vultr", "5M", "美国", "Miami")
    # addSSHConfig("1.13.247.142", 22, "ubuntu", "hitcs2020!", "国内节点1", "腾讯云", "5M", "中国", "南京")
    # addSSHConfig("1.13.192.245", 22, "ubuntu", "hitcs2020!", "国内节点2", "腾讯云", "5M", "中国", "南京")
    # addSSHConfig("146.56.222.170", 22, "ubuntu", "hitcs2020!", "国内节点3", "腾讯云", "5M", "中国", "南京")
    # setupServer("149.28.19.158")
    # setupServer("167.179.113.210")
    # setupServer("202.182.100.184")
    # setupServer("45.76.139.94")
    # setupServer("45.77.166.154")
    # setupServer("1.13.247.142")
    # setupServer("1.13.192.245")
    # setupServer("146.56.222.170")
    # createSubscription("订阅分组1")
    deleteLink("admin")
    # deleteSub("订阅分组2")

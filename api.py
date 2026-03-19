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
        "name": "国外随机链路1",
        "mask": "混合伪装",
        "encryption": "chacha20",
        "targetType": 1,
        "target": "国外",
        "linkLength": 2
    },
    {
        "types": "动态随机",
        "name": "国外随机链路2",
        "mask": "混合伪装",
        "encryption": "chacha20",
        "targetType": 1,
        "target": "国外",
        "linkLength": 2
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


url = 'http://49.232.164.17:3000/'


# 添加ssh配置
def addSSHConfig(ip, port: int, username, password: str, node_name, servicer, bandwidth, country, city=""):
    data_json = {"ip": ip, "port": port, "username": username, "password": encrypt(password), "node_name": node_name,
                 "servicer": servicer, "bandwidth": bandwidth, "country": country, "city": city}
    response = requests.post(url + "addSshConfig", json=data_json)
    return response.json()


def setupServer(ip):
    data_json = {"ip": ip}
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
    response = requests.post(url + "getLink", json=encrypt_dynamic(data_json))
    ret = response.json()
    print(ret)
    return decrypt_dynamic(ret["data"])


def deleteLink(username, link=None):
    data_json = {"username": username, 'link': link}
    response = requests.post(url + "deleteLink", json=encrypt_dynamic(data_json))
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


def addUserPermission(userList: list, subscriptionList: list):
    data_json = {"userList": userList, "subscriptionList": subscriptionList}
    response = requests.post(url + "addUserPermission", json=data_json)
    # print(response)
    return response.json()


def _proccess():
    """
    部署服务器的流程、模板。

    tips:
    如果没有正常删除用户链路，则需要改userlist中的used-links-count为0或为空
    如果创建订阅过程出错，则需要手动在数据库subscription表中删除该订阅，并手动在linkpool文件夹下删除该订阅的文件夹。
    """
    res = addSSHConfig("43.139.114.50", 22, "ubuntu", "hitcs2023!", "国内节点50", "腾讯云", "10M", "中国", "广州")
    res = setupServer("43.139.114.50")
    res = createSubscription("subscription")
    res = addUserPermission(['admin'], ['subscription'])
    res = getLink("subscription", "1", "admin")
    res = deleteLink("admin",
                     link={"rip": "42.193.106.150", "rport": "22975", "rcipher": "salsa20", "rkey": "jkGUAbutrE"})
    res = deleteLink("admin")
    res = deleteSub("subscription")

    print(res)


if __name__ == '__main__':
    # addSSHConfig("47.97.11.61", 22, "root", "hitcs2020!", "国内节点1", "阿里云", "5M", "中国", "杭州")
    # addSSHConfig("8.130.75.56", 22, "root", "hitcs2020!", "国内节点2", "阿里云", "5M", "中国", "乌兰察布")
    # addSSHConfig("152.136.50.230", 22, "ubuntu", "hitcs2020!", "国内节点2", "阿里云", "20M", "中国", "北京")
    # addSSHConfig("43.153.206.42", 22, "ubuntu", "hitcs2020!", "国外节点2", "腾讯云", "30M", "美国", "新加坡")
    # addSSHConfig("43.163.246.35", 22, "ubuntu", "hitcs2020!", "国外节点3", "腾讯云", "30M", "美国", "东京")
    # setupServer("47.97.11.61")
    setupServer("8.130.75.56")
    # setupServer("43.153.206.42")
    # setupServer("43.163.246.35")
    # setupServer("167.179.113.210")
    # setupServer("149.28.19.158")
    # res = createSubscription("subscription")
    # res = addUserPermission(['admin'], ['subscription'])
    # res=getLink("subscription",'0','admin')
    # res = deleteLink("admin",
    #                  link={"lip": "42.193.106.150", "lport": "22975", "lcipher": "salsa20", "lkey": "jkGUAbutrE"})
    # res = deleteLink("admin")
    # res = deleteSub("subscription")
    # deleteSub("订阅分组2")
    # print(res)

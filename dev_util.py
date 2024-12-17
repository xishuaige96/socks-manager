import json

import paramiko
import mysql.connector
from jiami import decrypt, encrypt
import re
import os
import pickle
from datetime import datetime
import base64
from Crypto.Cipher import AES

# 数据库配置信息
db_config = {
    'host': '127.0.0.1',
    # 'host': '47.95.38.164',
    'user': 'root',
    'password': 'hitcs2020!',
    'database': 'heartbeat',
}


def close_alice_screens(ip):
    read_node_configs()
    port = node_configs[ip][0]
    username = node_configs[ip][1]
    password = node_configs[ip][2]
    try:
        # 创建SSH客户端
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 连接服务器
        client.connect(hostname=ip, port=port,
                       username=username, password=password)

        # 执行命令获取screen列表
        _, stdout, _ = client.exec_command("screen -ls")
        screen_list = stdout.read().decode('utf-8')
        # print(screen_list)

        print(f'{ip}上已关闭的Alice窗口：')
        # 关闭以'Alice'开头的screen窗口
        for line in screen_list.split('\n'):
            match = re.search(r'Alice\d+', line)
            if match != None:
                screen_name = match.group()
                print(screen_name)
                client.exec_command(f"screen -S {screen_name} -X quit")

        # print(f"成功关闭{ip}上所有名称以'Alice'开头的screen窗口。")

    except paramiko.AuthenticationException:
        print("身份验证失败，请检查用户名和密码。")
    except paramiko.SSHException:
        print("SSH连接或执行命令时出现错误。")
    finally:
        client.close()


def read_node_configs():
    '''
    从数据库读取node_configs
    '''
    global node_configs
    node_configs = {}
    #
    # conn = mysql.connector.connect(**db_config)
    # cursor = conn.cursor()

    # cursor.execute(
    #     'SELECT ip,port,username,password,`bob-port`,`bob-password`,`bob-encrypt`,status from nodeconfig')
    # rows_nodeconfig = cursor.fetchall()
    #
    # cursor.close()
    # conn.close()
    #
    # # 将节点配置信息保存在node_configs内
    # for row in rows_nodeconfig:
    #     node_configs[row[0]] = row[1:]
    # # 解密
    # for key in node_configs.keys():
    #     node_configs[key] = (
    #         node_configs[key][0],
    #         node_configs[key][1],
    #         decrypt(node_configs[key][2]),
    #         node_configs[key][3],
    #         decrypt(node_configs[key][4]),
    #         node_configs[key][5],
    #         node_configs[key][6]
    #     )


def closeAllAlice():
    '''
    关闭数据库nodeconfig中记录的所有节点上的Alice，同时删除./userlink/port_dict
    '''
    read_node_configs()
    ip_list = node_configs.keys()
    for ip in ip_list:
        close_alice_screens(ip)
    os.remove('./userlink/port_dict')


def modify_port_dict():
    with open('./userlink/port_dict', 'rb') as file:
        port_dict = pickle.load(file)
    # 接下来是更改操作
    del port_dict['208.167.255.248']

    # 存入
    with open('./userlink/port_dict', 'wb') as file:
        pickle.dump(port_dict, file)


def encrypt_service_json(path):
    f = open(path, "r", encoding='utf-8')
    a = json.load(f)
    f.close()
    s = json.dumps(a)
    f = open(path, "w", encoding='utf-8')
    f.write(encrypt(s))


def read_subscription_json(subscriptionName):
    '''
    从/opt下读取加密了的订阅文件，解密后存储在当前路径下的temp_decripted_subsctiption.json
    '''
    with open(f'/opt/{subscriptionName}.json', 'r') as f:
        fileStr = f.read()
        jsonStr = decrypt(fileStr)
        subscription_data = json.loads(jsonStr)
        # encoding参数和下面的ensure_ascii参数是为了确保能够正确读取和显示中文
        with open('temp_decrypted_subsctiption.json', 'w', encoding='utf-8') as f2:
            json.dump(subscription_data, f2, ensure_ascii=False,
                      indent=4)  # indent参数是为了格式化json


def write_subscription_json(subscriptionName):
    '''
    将当前路径下的temp_decripted_subsctiption.json加密后保存在/opt下的<subscription>.json中
    '''
    with open('temp_decrypted_subsctiption.json', 'r') as f:
        subscription_data = json.load(f)
        with open(f'/opt/{subscriptionName}.json', 'w') as f2:
            f2.write(encrypt(json.dumps(subscription_data)))


def decrypt_in_zhongkong(cipher_data: dict) -> str:
    '''
    传入加密字典{"nonce":"...","ciphertext":"...","tag":"..."}
    返回字符串，可自行json.loads一下
    '''
    formatted_date = datetime.now().date().strftime("%Y%m%d")
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    nonce = base64.b64decode(cipher_data['nonce'])
    ciphertext = base64.b64decode(cipher_data['ciphertext'])
    tag = base64.b64decode(cipher_data['tag'])
    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    data = cipher.decrypt_and_verify(ciphertext, tag)
    data = data.decode()
    # data = json.loads(data.decode())
    return data


def encrypt_in_zhongkong(plain_data: str) -> dict:
    '''
    传入字符串，输出一个字典{"nonce":"...","ciphertext":"...","tag":"..."}
    '''
    formatted_date = datetime.now().date().strftime("%Y%m%d")
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(plain_data.encode())
    encrypted_data = {
        'nonce': base64.b64encode(cipher.nonce).decode('utf-8'),
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
        'tag': base64.b64encode(tag).decode('utf-8')
    }
    return encrypted_data


if __name__ == "__main__":
    read_subscription_json('server1')

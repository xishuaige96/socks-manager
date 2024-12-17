import base64
import configparser
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import requests
from Cryptodome.Cipher import AES
from Cryptodome.Cipher import PKCS1_OAEP
from Cryptodome.PublicKey import RSA

from client_util import send

import json


class myAES:
    def __init__(self, str_key):
        self.key = str_key

    def pad(self, data):
        block_size = AES.block_size
        padding_size = block_size - len(data) % block_size
        padding = bytes([padding_size] * padding_size)
        return data + padding

    def unpad(self, data):
        padding_size = data[-1]
        return data[:-padding_size]

    def encrypt_dict(self, data_dict):
        json_data = json.dumps(data_dict)
        json_data_bytes = json_data.encode('utf-8')

        key_bytes = self.key.encode('utf-8')
        cipher = AES.new(key_bytes, AES.MODE_ECB)

        encrypted_data = cipher.encrypt(self.pad(json_data_bytes))
        return base64.b64encode(encrypted_data).decode('utf-8')

    def decrypt_dict(self, encrypted_data):
        encrypted_data_bytes = base64.b64decode(encrypted_data)

        key_bytes = self.key.encode('utf-8')
        cipher = AES.new(key_bytes, AES.MODE_ECB)

        decrypted_data = self.unpad(cipher.decrypt(encrypted_data_bytes))
        return json.loads(decrypted_data)


def decryption_AES(response, k="data"):
    dd = response.json()[k]
    formatted_date = datetime.now().date().strftime("%Y%m%d")
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    nonce = base64.b64decode(dd['nonce'])
    ciphertext = base64.b64decode(dd['ciphertext'])
    tag = base64.b64decode(dd['tag'])
    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    data = cipher.decrypt_and_verify(ciphertext, tag)
    data = json.loads(data.decode())
    return data


def encryption_AES(data):
    data_str = json.dumps(data)
    formatted_date = datetime.now().date().strftime("%Y%m%d")
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


def encrypt_ini_file(input_file, output_file, key):
    # 从未经加密的ini中解析出字典
    config = configparser.ConfigParser()
    config.read(input_file)

    data_dict = {}
    for section in config.sections():
        data_dict[section] = dict(config[section])

    myaes = myAES(key)
    data_str = myaes.encrypt_dict(data_dict)

    # 把加密之后的字符串写进加密ini
    config = configparser.ConfigParser()
    config['EncryptedData'] = {'data': data_str}

    with open(output_file, 'w') as f:
        config.write(f)


def decrypt_ini_to_json(input_file, key):
    config = configparser.ConfigParser()
    config.read(input_file)

    encrypted_data = config.get('EncryptedData', 'data')
    myaes = myAES(key)
    data_dict = myaes.decrypt_dict(encrypted_data)
    return data_dict


def login(logInfo):
    ini_json = get_ini_json()

    url = str(ini_json["server"]["ip"]) + ":" + str(ini_json["server"]["port"]) + "/" + \
          str(ini_json["server"]["login_path"])
    try:
        # response = requests.post(url, json=logInfo)
        response=send('POST',json=logInfo)
    except:
        return '由于目标计算机积极拒绝，无法连接。'
    if (response.status_code == 200):
        data = decryption_AES(response)
        return data
    else:
        return response.text


def add_sub(dict_list, username):
    data = {'user': username,
            "address": dict_list}
    encrypted_data = encryption_AES(data)

    ini_json = get_ini_json()

    url = str(ini_json["server"]["ip"]) + ":" + str(ini_json["server"]["port"]) + "/" + \
          str(ini_json["server"]["userupdate_subscription_path"])

    # response = requests.post(url, json=encrypted_data)
    response=send('POST',json=encrypted_data)
    if (response.status_code == 200):
        return True
    else:
        return False


def get_ini_json(key="hello_socks_ab_!"):
    decrypted_data = decrypt_ini_to_json("ini/encrypted_center_control.ini", key=key)
    return decrypted_data


def buildLink(request_data):
    encrypted_data = encryption_AES(request_data)

    ini_json = get_ini_json()

    url = str(ini_json["server"]["ip"]) + ":" + str(ini_json["server"]["port"]) + "/" + \
          str(ini_json["server"]["buildlink"])

    # response = requests.post(url, json=encrypted_data)
    response=send('POST',json=encrypted_data)
    if (response.status_code == 200):
        response = decryption_AES(response)
        print("buildlink连接成功")
        return response
    else:
        return []


def deleteLink(request_data):
    ini_json = get_ini_json()

    url = str(ini_json["server"]["ip"]) + ":" + str(ini_json["server"]["port"]) + "/" + \
          str(ini_json["server"]["deletelink"])

    # response = requests.post(url, json=request_data)
    response=send('POST',json=request_data)
    if (response.status_code == 200):
        print("已经断开")
        return True
    else:
        return False

# key = "hello_socks_ab_!"  # 16字节长度的AES密钥
#
# # 假设有一个名为 "config.ini" 的明文 INI 文件
# input_file = "ini/center_control.ini"
#
# # 将明文 INI 文件加密为 "encrypted_config.ini"
# encrypt_ini_file(input_file, "ini/encrypted_center_control.ini", "hello_socks_ab_!")
#
# print(get_ini_json())

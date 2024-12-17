from Crypto.Cipher import AES
import json
import base64

key_str = 'hitcs2020!123456'
key = key_str.encode()


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


def decrypt(ciphertext: str):
    # 解码 Base64 编码的字符串
    decoded_data = base64.b64decode(ciphertext)

    encrypted_data = json.loads(decoded_data)

    # 现在我们来解密数据
    nonce = base64.b64decode(encrypted_data['nonce'])
    ciphertext = base64.b64decode(encrypted_data['ciphertext'])
    tag = base64.b64decode(encrypted_data['tag'])

    # 创建一个新的cipher对象用于解密
    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)

    # 解密数据
    data = cipher.decrypt_and_verify(ciphertext, tag)
    return data.decode()


if __name__ == '__main__':
    ciphertext = encrypt('Hello, world!')
    print(ciphertext)
    plaintext = decrypt(ciphertext)
    print(plaintext)

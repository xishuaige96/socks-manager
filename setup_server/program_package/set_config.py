import json
import sys

# 要写入的数据
config = {
    'lcipher': 'chacha20',
    'lkey': '123456',
    'lip': '0.0.0.0',  # 这个写死
    'lport': '1080',
    'rcipher': 'salsa20',
    'rkey': '654321',
    'rip': '127.0.0.1',
    'rport': '1080'
}

if __name__ == '__main__':
    args = sys.argv[1:]  # 执行该文件时的命令行参数，除去第一个（文件名）
    config['lport'], config['lcipher'], config['lkey'], config['rip'], config['rport'], config['rcipher'], config['rkey'] = args
    config = {k: v for k, v in config.items() if v != 'None'}
    # 端口需要是数字！！
    config['lport'] = int(config['lport'])
    if 'rport' in config.keys():
        config['rport'] = int(config['rport'])

    # 写入 JSON 文件
    with open(f'config{config["lport"]}.json', 'w') as file:
        json.dump(config, file)

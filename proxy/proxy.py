from flask import Flask, request
import requests

app = Flask(__name__)

# 主服务器的地址
main_server_url = "http://47.95.38.164:3000"


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    # 构建主服务器的完整请求URL
    url = f"{main_server_url}/{path}"

    # 获取用户请求的方法
    method = request.method

    # 获取用户请求的头部信息
    headers = dict(request.headers)

    # 获取用户请求的数据
    data = request.get_data()

    # 发送请求给主服务器
    response = requests.request(method, url, headers=headers, data=data)

    # 将主服务器的响应原样返回给用户
    return response.content, response.status_code, response.headers.items()


if __name__ == '__main__':
    # 启动代理服务器
    app.run(port=5000, host='0.0.0.0')

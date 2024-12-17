from flask import Flask, request, jsonify
import json

app = Flask(__name__)


def authenticate(authcode):
    """
    鉴定客户端的认证码
    """
    return authcode=='123456'


@app.route('/getServerList', methods=['POST'])
def get_server_list():
    """
    获取代理服务器列表服务
    """
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    authcode = data.get('authcode', None)

    if authcode is None:
        return jsonify({"message": "Missing 'authcode' in request"}), 400
    
    if not authenticate(authcode):
        return jsonify({"message": "认证失败"}), 403

    try:
        with open('./config/proxy_server_list.json','r') as f:
            response_data=json.load(f)
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({"message": f"Error getting proxy_server_list: {str(e)}"}), 500


if __name__ == '__main__':
    # 启动代理服务器
    app.run(port=5001)

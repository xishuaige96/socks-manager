from datetime import datetime
from Crypto.Cipher import AES
import json
import base64
from flask import Flask, request, jsonify, abort
import time
import mysql.connector.pooling
from router import buildLink, deleteLink, resetAllBob, closeBob, setBob_randomly, getCountryFlag, delete_Bob
from util_zhongkong import get_subscription_userlist, write_userlist, InfoException, insert_subscription, \
    delete_subscription, insert_linknodelist, addUserPermission, get_used_links_count, set_used_links_count, \
    add_used_links_count, delete_node_in_database
from jiami import encrypt, decrypt
from link_pool import onSubscriptionCreated, onSubscriptionDeleted, getLink
from setup_server import insertSSHConfigToDatabase, setup_server

app = Flask(__name__)

db_config = {
    # 'host': '47.95.38.164',
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'hitcs2020!',
    'database': 'heartbeat',
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="main_pool", pool_size=32, **db_config)

max_used_links_count_limit = 5


@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    node_ip = request.remote_addr
    send_time = float(request.args.get('time', None))
    if send_time is None:
        return '', 403
    receive_time = time.time()
    latency = (receive_time - send_time) * 1000
    cpu_percent = float(request.args.get('cpu_percent'))
    memory_usage = float(request.args.get('memory_usage'))
    memory_percent = float(request.args.get('memory_percent'))
    network_upload_speed = float(request.args.get('network_upload_speed'))
    network_download_speed = float(request.args.get('network_download_speed'))
    live_flag = int(request.args.get('live_flag'))

    connection = connection_pool.get_connection()
    cursor = connection.cursor()

    try:
        select_query = "SELECT * FROM server where serverip = '%s'" % node_ip
        cursor.execute(select_query)
        result = cursor.fetchone()
        if result is None:
            try:
                insert_query = "INSERT INTO server (serverip, ping, cpu, memory, `memory-rate`, `net-download`, " \
                               "`net-upload`, " \
                               "`live-flag`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                values = (
                    node_ip, latency, cpu_percent, memory_usage, memory_percent, network_download_speed,
                    network_upload_speed, live_flag)
                cursor.execute(insert_query, values)
                connection.commit()
                # print("Data inserted successfully!")
            except mysql.connector.Error as error:
                print("Error inserting data: {}".format(error))
                connection.rollback()
                cursor.close()
                connection.close()
                return '', 403
        else:
            now_id = result[0]
            try:
                update_query = "UPDATE server SET ping = %s, cpu = %s, memory = %s, `memory-rate` = %s, " \
                               "`net-download` = %s, `net-upload` = %s, `live-flag` = %s WHERE id = %s"
                values = (
                    latency, cpu_percent, memory_usage, memory_percent, network_download_speed, network_upload_speed,
                    live_flag, now_id)
                cursor.execute(update_query, values)
                connection.commit()
                # print("Data updated successfully!")
            except mysql.connector.Error as error:
                print("Error updating data: {}".format(error))
                connection.rollback()
                cursor.close()
                connection.close()
                return '', 403
        # print("Query executed successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        return '', 403

    cursor.close()
    connection.close()

    # print(f'Received heartbeat from {node_ip} at {time.ctime(receive_time)}, latency: {latency} seconds')

    return '', 200


@app.route('/server', methods=['POST'])
def server():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    user = data.get('user', None)
    addr = data.get('addr', None)

    if user is None or addr is None:
        return jsonify({"message": "Missing 'user' or 'addr' in request"}), 400
    userlist = None
    # 验证用户是否有该服务的权限
    try:
        userlist = get_subscription_userlist(
            connection_pool.get_connection(), addr)
    except InfoException as e:
        if e.info == 0:
            abort(403)
        elif e.info == 1:
            return '', 403
    if userlist is None:
        abort(403)
    if user not in userlist:
        abort(403)

    try:
        with open(f'/opt/{addr}.json', 'r') as f:
            jsonStr = f.read()
            jsonStr = decrypt(jsonStr)
            response_data = json.loads(jsonStr)
            # response_data = json.load(f)
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({"message": f"Error reading server.json: {str(e)}"}), 500


@app.route('/server1', methods=['POST'])
def server1():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    user = data.get('user', None)

    if user is None:
        return jsonify({"message": "Missing 'user' in request"}), 400

    if user == 'admin':
        try:
            with open('/opt/server1.json', 'r') as f:
                response_data = json.load(f)
            return jsonify(response_data), 200
        except Exception as e:
            return jsonify({"message": f"Error reading server.json: {str(e)}"}), 500
    else:
        abort(403)


@app.route('/server2', methods=['POST'])
def server2():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    user = data.get('user', None)

    if user is None:
        return jsonify({"message": "Missing 'user' in request"}), 400

    if user == 'admin':
        try:
            with open('/opt/server2.json', 'r') as f:
                response_data = json.load(f)
            return jsonify(response_data), 200
        except Exception as e:
            return jsonify({"message": f"Error reading server.json: {str(e)}"}), 500
    else:
        abort(403)


@app.route('/createSubscription', methods=['POST'])
def createSubscription():
    '''
    创建一个类似于server1的服务，然后在/opt下添加.json文件
    '''
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data_ = request.get_json()
    subscriptionName = data_.get('subscriptionName', None)
    data = data_.get('data', None)

    if subscriptionName is None or data is None:
        return jsonify({"message": "Missing 'subscriptionName' or 'data' in request"}), 400

    try:
        # 通过查询userlist来判断该订阅是否存在
        userlist = get_subscription_userlist(
            connection_pool.get_connection(), subscriptionName)
        if userlist != None:
            # 数据库已有该订阅
            return jsonify({"message": "Subscription already exists!"}), 500
        with open(f'/opt/{subscriptionName}.json', 'w') as file:
            file.write(data)
        insert_subscription(connection_pool.get_connection(), subscriptionName)
        onSubscriptionCreated(subscriptionName)
    except Exception as e:
        return jsonify({"message": f"Error while creating subscription: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/deleteSubscription', methods=['POST'])
def deleteSubscription():
    '''
    删除一个订阅
    '''
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    subscriptionName = data.get('subscriptionName', None)

    if subscriptionName is None:
        return jsonify({"message": "Missing 'subscriptionName' in request"}), 400

    try:
        delete_subscription(connection_pool.get_connection(), subscriptionName)
        onSubscriptionDeleted(subscriptionName)
    except Exception as e:
        return jsonify({"message": f"Error while deleting subscription: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/getLink', methods=['POST'])
def run_getLink():
    '''
    为用户从链路池获取一条链路
    '''
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    try:
        formatted_date = datetime.now().date().strftime("%Y%m%d")
        key_str = 'hitskey' + formatted_date + '!'
        key = key_str.encode()
        nonce = base64.b64decode(data['nonce'])
        ciphertext = base64.b64decode(data['ciphertext'])
        tag = base64.b64decode(data['tag'])
        cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
        data = cipher.decrypt_and_verify(ciphertext, tag)
        data = json.loads(data.decode())
    except Exception as e:
        return jsonify({"message": "Server Error: " + str(e)}), 500

    subscriptionName = data.get('subscriptionName', None)
    linkMethodId = str(data.get('linkMethodId', None))
    username = data.get('username', None)

    if subscriptionName is None or linkMethodId is None or username is None:
        return jsonify({"message": "Missing 'subscriptionName' or 'linkMethodId' or 'username' in request"}), 400

    try:
        userlist = get_subscription_userlist(
            connection_pool.get_connection(), subscriptionName)
        if username not in userlist:
            # 用户没有该订阅分组的使用权限
            return jsonify({"message": "The user does not have permission to use this subscription."}), 500
        old_used_links_count = get_used_links_count(connection_pool.get_connection(), username)
        if old_used_links_count >= max_used_links_count_limit:
            return jsonify({"message": "用户使用的链路数已满额."}), 500
        ret = getLink(subscriptionName, linkMethodId, username)
        set_used_links_count(connection_pool.get_connection(), username, old_used_links_count + 1)
    except Exception as e:
        return jsonify({"message": f"Error while getting link from linkpool: {str(e)}"}), 500

    data_str = json.dumps(ret)
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(data_str.encode())
    encrypted_data = {
        'nonce': base64.b64encode(cipher.nonce).decode('utf-8'),
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
        'tag': base64.b64encode(tag).decode('utf-8')
    }

    return jsonify({"data": encrypted_data, "message": "ok"}), 200


@app.route('/signup', methods=['POST'])
def signup():
    '''
    注册，填写数据库
    '''
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    # 必选信息
    username = data.get('username', None)
    passwd = data.get('passwd', None)
    # 可选信息
    phone = data.get('phone', None)
    department = data.get('department', None)
    grade = data.get('grade', None)

    if username is None or passwd is None:
        return jsonify({"message": "Missing 'username' or 'account' or 'passwd' in request"}), 400

    try:
        write_userlist(connection_pool.get_connection(),
                       username, passwd, phone, department, grade)
    except InfoException:
        return '', 403

    return jsonify({"message": "ok"}), 200


@app.route('/alicelogin', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    user = data.get('user', None)
    passwd = data.get('passwd', None)

    if user is None:
        return jsonify({"message": "Missing JSON in request"}), 400

    connection = connection_pool.get_connection()
    cursor = connection.cursor()

    select_query = "SELECT passwd FROM userlist where username = '%s'" % user
    cursor.execute(select_query)
    result = cursor.fetchone()

    if result is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "No user in database"}), 400
    else:
        if result[0] == passwd:
            select_query = "SELECT address FROM `user-address` where user = '%s'" % user
            cursor.execute(select_query)
            try:
                result = eval(cursor.fetchone()[0])
                data_str = json.dumps(result)
            except:
                data_str = json.dumps({})
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
            return jsonify({"message": "ok", "data": encrypted_data}), 200
        else:
            cursor.close()
            connection.close()
            return jsonify({"message": "Wrong passwd"}), 401


@app.route('/userupdate-subscription', methods=['POST'])
def addsubscription():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    try:
        formatted_date = datetime.now().date().strftime("%Y%m%d")
        key_str = 'hitskey' + formatted_date + '!'
        key = key_str.encode()
        nonce = base64.b64decode(data['nonce'])
        ciphertext = base64.b64decode(data['ciphertext'])
        tag = base64.b64decode(data['tag'])
        cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
        data = cipher.decrypt_and_verify(ciphertext, tag)
        data = json.loads(data.decode())
    except Exception as e:
        return jsonify({"message": "Server Error: " + str(e)}), 500

    user = data.get('user', None)
    address = data.get('address', None)

    if user is None:
        return jsonify({"message": "Missing JSON in request"}), 400

    connection = connection_pool.get_connection()
    cursor = connection.cursor()

    select_query = "SELECT id FROM `user-address` where user = '%s'" % user
    cursor.execute(select_query)
    result = cursor.fetchone()

    if result is None:

        insert_query = """INSERT INTO `user-address` (user, address) VALUES (%s, %s)"""
        values = (user, str(address))
        cursor.execute(insert_query, values)
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"message": "ok"}), 200

    else:
        try:
            update_query = """UPDATE `user-address` SET address = "%s" WHERE id = '%s'""" % (
                str(address), result[0])
            cursor.execute(update_query)
            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({"message": "ok"}), 200
        except Exception as e:
            cursor.close()
            connection.close()
            return jsonify({"message": "Server Error: " + str(e)}), 500


@app.route('/buildLink', methods=['POST'])
def run_buildLink():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    try:
        formatted_date = datetime.now().date().strftime("%Y%m%d")
        key_str = 'hitskey' + formatted_date + '!'
        key = key_str.encode()
        nonce = base64.b64decode(data['nonce'])
        ciphertext = base64.b64decode(data['ciphertext'])
        tag = base64.b64decode(data['tag'])
        cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
        data = cipher.decrypt_and_verify(ciphertext, tag)
        data = json.loads(data.decode())
    except Exception as e:
        return jsonify({"message": "Server Error: " + str(e)}), 500
    # username: str, linkLength: int, targetType: int, target: str
    username = data.get('username', None)
    linkLength = data.get('linkLength', None)
    targetType = data.get('targetType', None)
    target = data.get('target', None)

    if username is None or linkLength is None or targetType is None or target is None:
        return jsonify({"message": "Incorrect parameters in request"}), 400

    try:
        ret = buildLink(username, linkLength, targetType, target)
    except Exception as e:
        return jsonify({"message": f"Error while building link: {str(e)}"}), 500

    data_str = json.dumps(ret)
    key_str = 'hitskey' + formatted_date + '!'
    key = key_str.encode()
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(data_str.encode())
    encrypted_data = {
        'nonce': base64.b64encode(cipher.nonce).decode('utf-8'),
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
        'tag': base64.b64encode(tag).decode('utf-8')
    }

    # ret是一个列表
    return jsonify({"data": encrypted_data, "message": "ok"}), 200


@app.route('/deleteLink', methods=['POST'])
def run_deleteLink():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()

    username = data.get('username', None)
    links = data.get('links', None)

    if username is None:
        return jsonify({"message": "Incorrect parameters in request"}), 400

    try:
        successfully_delete_count = deleteLink(username, links)
        add_used_links_count(connection_pool.get_connection(), connection_pool.get_connection(), username,
                             -1 * successfully_delete_count)
    except Exception as e:
        return jsonify({"message": f"Error while deleting link: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/resetallbob', methods=['GET'])
def run_resetAllBob():
    try:
        errors = resetAllBob()
    except Exception as e:
        return jsonify({"message": f"Error while resetting all Bob: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/closebob', methods=['POST'])
def run_closeBob():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()

    ip = data.get('ip', None)

    if ip is None:
        return jsonify({"message": "Incorrect parameters in request"}), 400

    try:
        closeBob(ip)
    except Exception as e:
        return jsonify({"message": f"Error while closing Bob: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/setbob', methods=['POST'])
def run_setBob():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()

    ip = data.get('ip', None)

    if ip is None:
        return jsonify({"message": "Incorrect parameters in request"}), 400

    try:
        setBob_randomly(ip)
    except Exception as e:
        return jsonify({"message": f"Error while setting Bob: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/addSshConfig', methods=['POST'])
def addSSHConfig():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    ip = data.get('ip', None)
    port = int(data.get('port', None))
    username = data.get('username', None)
    password = data.get('password', None)

    node_name = data.get('node_name', None)
    servicer = data.get('servicer', None)
    bandwidth = data.get('bandwidth', None)
    country = data.get('country', None)
    city = data.get('city', "")

    if ip is None or port is None or username is None or password is None or node_name is None or servicer is None or bandwidth is None or country is None:
        return jsonify({"message": "Incorrect parameters in request"}), 400

    try:
        insertSSHConfigToDatabase(ip, port, username, password)
    except Exception as e:
        return jsonify({"message": f"Error while inserting SSH config to database: {str(e)}"}), 500

    try:
        insert_linknodelist(connection_pool.get_connection(), node_name, servicer, ip, bandwidth, country + city,
                            getCountryFlag(country))
    except Exception as e:
        return jsonify({"message": f"Error while inserting data to linknodelist table: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/setupServer', methods=['POST'])
def setupServer():
    '''
    为新的节点服务器运行安装脚本。需要先在数据库中插入SSH配置！
    '''
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()

    # ip, bob_port: int, bob_password, bob_encrypt_method,shouldRandom:bool = False
    ip = data.get('ip', None)
    bob_port = data.get('port', None)
    bob_password = data.get('bob_password', None)
    bob_encrypt_method = data.get('bob_encrypt_method', None)
    shouldRandom = data.get('shouldRandom', None)

    if ip is None:
        return jsonify({"message": "Missing ip in request"}), 400
    if (shouldRandom is None or shouldRandom is False) and (
            bob_port is None or bob_password is None or bob_encrypt_method is None):
        return jsonify({"message": "Incorrect parameters in request"}), 400

    try:
        setup_server(ip, bob_port, bob_password,
                     bob_encrypt_method, shouldRandom)
    except Exception as e:
        return jsonify({"message": f"Error while setting up server: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/changepasswd', methods=['POST'])
def change_passwd():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()
    username = data.get('username', None)
    old_password = data.get('old_password', None)
    new_password = data.get('new_password', None)

    if username is None or old_password is None or new_password is None:
        return jsonify({"message": "Missing parameters in request"}), 400

    connection = connection_pool.get_connection()
    cursor = connection.cursor()
    select_query = "SELECT passwd FROM userlist where username = '%s'" % username
    cursor.execute(select_query)
    result = cursor.fetchone()

    if result is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "No user in database"}), 400
    else:
        if result[0] == old_password:
            try:
                update_query = "UPDATE userlist SET passwd = '%s' WHERE username = '%s'" % (new_password, username)
                cursor.execute(update_query)
                connection.commit()
                cursor.close()
                connection.close()
                return jsonify({"message": "ok"}), 200
            except Exception as e:
                cursor.close()
                connection.close()
                return jsonify({"message": "Server Error: " + str(e)}), 500
        else:
            cursor.close()
            connection.close()
            return jsonify({"message": "Wrong old passwd"}), 401


@app.route('/addUserPermission', methods=['POST'])
def run_addUserPermission():
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()

    userList = data.get('userList', None)
    subscriptionList = data.get('subscriptionList', None)

    if userList is None or subscriptionList is None:
        return jsonify({"message": "Missing parameters in request"}), 400

    try:
        addUserPermission(connection_pool.get_connection(), userList, subscriptionList)
    except Exception as e:
        return jsonify({"message": f"Error while adding user permission: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


@app.route('/deletenode', methods=['POST'])
def delete_node():
    """
    删除节点。清空节点上的文件信息，删除数据库该节点的所有记录。
    """
    if not request.is_json:
        return jsonify({"message": "Missing JSON in request"}), 400

    data = request.get_json()

    ip = data.get('ip', None)

    if ip is None:
        return jsonify({"message": "Missing parameters in request"}), 400

    try:
        # closeBob(ip, True)
        delete_Bob(ip)
        delete_node_in_database(connection_pool.get_connection(), ip)
    except Exception as e:
        return jsonify({"message": f"Error while deleting node: {str(e)}"}), 500

    return jsonify({"message": "ok"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

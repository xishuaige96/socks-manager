'''
负责路由选择，以及保存各个节点Alice端口空间使用情况。
2.1 8月7日
'''
import re
import mysql.connector.pooling
import random
import paramiko
import os
import json
import pickle
from jiami import decrypt, encrypt
import traceback
import string

db_config = {
    'host': '47.95.38.164',
    # 'host': '127.0.0.1',
    'user': 'root',
    'password': 'hitcs2020!',
    'database': 'heartbeat',
}
connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="router_pool", pool_size=20, **db_config)

country_list = {
    '中国': 0,
    '国外': 1,
    '美国': 2,
    '日本': 3
}

bob_method_list = [
    'chacha20',
    'salsa20'
]

country_ips = {}  # 数字到ip集合的字典
# country_ips样例：
# country_ips[country_list['中国']] = [
#     '49.232.253.70',
#     '110.42.209.65',
#     '124.221.221.133'
# ]

node_configs = {}
# node_configs样例
# node_configs = {
#     '49.232.253.70': (  # 北京计费49
#         '22', # ssh连接的端口
#         'ubuntu', # 用户名
#         'hitcs2020!', # 密码
#         '1082', # 本地Bob的端口
#         '123456', # Bob的密码
#         'chacha20', # Bob的加密方式
#     )
# }


# 用于保存每个节点已使用的端口
# 是一个字典，字典的值是集合，集合内存储int类型。字典的键是str类型
port_dict = None

need_rollback_port = False
need_rollback_Alice = False
need_rollback_inLinkNum = False
need_rollback_Bob_port = False

ssh_connection_cache = {}


class ShowToUserException(Exception):
    '''
    这类异常是要展示给用户的
    '''

    def __init__(self, message, type=0) -> None:
        super().__init__(message)
        # type：1为closeBob时Bob正在使用异常
        self.type = type


class StoreRollbackDataException(Exception):
    '''
    当另一个异常出现时，能够在该类中存储这个异常以及其他数据

    主要为了服务rollback_for_buildLink。
    在createLink中，link作为参数返回，出错后buildLink里的rollback_for_buildLink要用到该link参数。
    但若在createLink中就抛出异常而没有执行return返回，则调用rollback_for_buildLink(link)会出现link未定义异常。
    '''

    def __init__(self, data, exception) -> None:
        self.data = data
        self.exception = exception


def getCountryFlag(countryName: str):
    '''
    输入中文的国家名称，返回国家代码
    '''
    return country_list.get(countryName)


def read_node_configs():
    '''
    从数据库nodeconfig表和bobstatus表中读取数据存到node_configs全局变量中
    '''
    global node_configs
    node_configs = {}

    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()

        cursor.execute('SELECT ip,port,username,password FROM nodeconfig')
        rows_ssh = cursor.fetchall()
        cursor.execute('SELECT ip,port,password,method FROM bobstatus')
        rows_bob = cursor.fetchall()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()

    # 将节点配置信息保存在node_configs内
    for row in rows_ssh:
        node_configs[row[0]] = row[1:]
    for row in rows_bob:
        if row[0] not in node_configs.keys():
            print(f'Warning: {row[0]}在bobstatus表中却不在nodeconfig表中')
            # raise ShowToUserException('bobstatus表与nodeconfig表不匹配')
        else:
            # node_configs[row[0]].extend(row[1:])
            node_configs[row[0]] = (
                node_configs[row[0]][0],
                node_configs[row[0]][1],
                node_configs[row[0]][2],
                row[1],
                row[2],
                row[3],
            )
    # 解密
    for key in node_configs.keys():
        # 后面的Bob配置可能没有
        if len(node_configs[key]) == 6:
            node_configs[key] = (node_configs[key][0], node_configs[key][1], decrypt(
                node_configs[key][2]), node_configs[key][3], decrypt(node_configs[key][4]), node_configs[key][5])
        else:
            node_configs[key] = (
                node_configs[key][0], node_configs[key][1], decrypt(node_configs[key][2]))


def read_country_ips():
    '''
    从数据库读取country_ips
    '''
    global country_ips
    country_ips = {}

    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()

        cursor.execute('SELECT ip,`country-flag` FROM linknodelist')
        rows_ips = cursor.fetchall()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()

    # 将ip，国家信息保存进country_ips内
    for row in rows_ips:
        if row[1] not in country_ips.keys():
            country_ips[row[1]] = set()
        country_ips[row[1]].add(row[0])

    # 计算“国外”节点集合
    country_ips[country_list['国外']] = set()
    for country_id in country_ips.keys():
        if country_id == country_list['中国'] or country_id == country_list['国外']:
            continue
        country_ips[country_list['国外']
        ] |= country_ips[country_id]  # 集合并操作


def createNewSSHClient(hostname, port, username, password):
    '''
    创建一个ssh连接
    '''
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, port=port,
                       username=username, password=password)
        client.get_transport().set_keepalive(60)
        return client
    except:
        raise ShowToUserException('SSH连接失败')


def checkSSHConnectionAlive(hostname) -> bool:
    '''
    判断ssh连接是否存在，或是否可用
    '''
    if hostname not in ssh_connection_cache.keys():
        return False
    client = ssh_connection_cache[hostname]
    try:
        client.exec_command('ls')
    except Exception:
        return False
    return True


def run_commands_on_remote_host(hostname, port, username, password, commands):
    if checkSSHConnectionAlive(hostname) == False:
        ssh_connection_cache[hostname] = createNewSSHClient(
            hostname, port, username, password)

    client = ssh_connection_cache[hostname]

    for command in commands:
        stdin, stdout, stderr = client.exec_command(command)
        # print(stdout.read().decode()) # 什么都没输出也会有一行
        # output = stdout.read().decode()
        # if output != '':
        #     # 正常情况这里只会输出No such screen ...。即执行screen -X -S Alice{config[4]} quit语句时的警告
        #     print(f'Output of "{command}":\n{output}', end='')

    client.close()


def run_Socks_Alice(config):
    '''
    config为列表，按顺序为[0]Alice所在服务器ip，[1]Alice所在服务器接收远程控制的端口，[2]远程控制的用户名，[3]远程控制密码，[4]~[8]为Alice参数，[9]为SocksAB-1.0.3-alpha-01的前驱目录
    所有项均为字符串
    '''
    path = '/root' if config[2] == 'root' else f'/home/{config[2]}'
    commands = [
        f'screen -X -S Alice{config[4]} quit',  # 保险起见，先关闭可能存在的screen
        f'screen -dmS Alice{config[4]}',  # 覆盖创建、创建后不进入screen内
        f'screen -S Alice{config[4]} -X stuff "cd {path}/SocksAB/bin\n"',
        f'screen -S Alice{config[4]} -X stuff "python3 set_alice_config.py {config[4]} {config[5]} {config[6]} {config[7]} {config[8]} {config[9]} {config[10]}\n"',
        f'screen -S Alice{config[4]} -X stuff "./Socks-Alice alice_config.json\n"',
        f'screen -dmS Alice{config[4]}remove',
        f'screen -S Alice{config[4]}remove -X stuff "sleep 10\n"',
        f'screen -S Alice{config[4]}remove -X stuff "rm -f {path}/SocksAB/conf/alice_config.json\n"',
        f'screen -X -S Alice{config[4]}remove quit',
    ]
    run_commands_on_remote_host(config[0], int(
        config[1]), config[2], config[3], commands)


def run_Socks_Bob(config):
    '''
    创建Bob。这里的config和run_Socks_Alice的config不一样
    '''
    path = '/root' if config[2] == 'root' else f'/home/{config[2]}'
    commands = [
        f'screen -X -S Bob quit',  # 保险起见，先关闭可能存在的Bob
        f'screen -dmS Bob',  # 覆盖创建、创建后不进入screen内
        f'screen -S Bob -X stuff "cd {path}/SocksAB/bin\n"',
        f'screen -S Bob -X stuff "python3 set_bob_port.py {config[4]}\n"',
        f'screen -S Bob -X stuff "./Socks-Bob -p {config[4]} -k {config[5]} -m {config[6]}\n"',
    ]
    run_commands_on_remote_host(config[0], int(
        config[1]), config[2], config[3], commands)


def destroy_Socks_Alice(config):
    '''
    参数同run_Socks_Alice
    '''
    commands = [
        f'screen -X -S Alice{config[4]} quit'
    ]
    run_commands_on_remote_host(config[0], int(
        config[1]), config[2], config[3], commands)


def destroy_Socks_Bob(config):
    '''
    接收参数sshconfig
    '''
    commands = [
        f'screen -X -S Bob quit'
    ]
    run_commands_on_remote_host(config[0], int(
        config[1]), config[2], config[3], commands)


def createAlices(configs):
    '''
    configs为Alice列表，每一项又为一个列表，描述一个Alice。
    configs[0]是给客户端的Alice
    '''
    global need_rollback_Alice
    need_rollback_Alice = True
    for config in configs[1:]:  # configs第一个是给客户端的
        run_Socks_Alice(config)


def destroyAlices(configs):
    for config in configs[1:]:
        destroy_Socks_Alice(config)


def getRandomPort():
    # 0~1023是熟知端口，1024~49151是注册端口，49152~65535是动态、私有端口
    return random.randint(10000, 30000)


def getUnlivedNodeSet():
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT serverip FROM server WHERE `live-flag`=0')
        result = cursor.fetchall()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()

    result = {i[0] for i in result}  # 元组转集合
    return result


def chooseNode(link: list, country: int, exit_ip):
    '''
    选择一个节点
    link里包含前驱节点
    country: 选取节点的范围。对应country_list里的值
    '''
    selected_node = {i[1] for i in link}  # 已选的节点ip集合
    # 把出口ip提前算进已选节点
    if exit_ip != None:
        selected_node.add(exit_ip)
    unlived_node = getUnlivedNodeSet()  # 无法与中控连通的节点集合
    ip_pool = country_ips[country] - selected_node - unlived_node  # 可选节点ip集合
    if len(ip_pool) == 0:
        print(f'为链路选择节点时出现异常，已选节点列表为：{link}')
        raise ShowToUserException('可选节点为空')
    ip_pool = list(ip_pool)
    link.append(['-1', random.choice(ip_pool), '-1'])


def getUnusedPort(ip: str) -> int:
    '''
    获取该ip下的一个随机的未使用的端口号
    '''
    # global port_dict
    if ip in port_dict:
        counter = 0
        newPort = getRandomPort()
        while newPort in port_dict[ip]:
            counter += 1
            # 尝试100次
            if counter >= 100:
                print(f'Error: {ip}节点端口号不足')
                raise ShowToUserException('节点端口号不足')
            newPort = getRandomPort()
    else:
        port_dict[ip] = set()  # set，也是一种哈希表，能够快速执行增删查操作
        newPort = getRandomPort()
    return newPort


def mallocPort(ip: str) -> str:
    '''
    从指定节点处申请一个空闲的端口号。
    '''
    # global port_dict
    newPort = getUnusedPort(ip)
    port_dict[ip].add(newPort)
    return str(newPort)


def freePort(ip: str, port: str):
    # 用discard不会抛出异常，用remove会抛出异常
    try:
        port_dict[ip].remove(int(port))
    # 异常可能为port_dict里找不到ip这个键，或port_dict[ip]这个集合里找不到这个port
    except Exception as e:
        print(f'Warning: 删除已使用端口时出错。{ip}无已使用的{port}端口')
    else:
        if port_dict[ip] == set():  # 为空集
            port_dict.pop(ip)  # 删除这个键


def add_Bob_inLinkNum(link):
    '''
    为数据库里的Bob的参与链路数量加一
    '''
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        for bobIp in [i[1] for i in link]:
            cursor.execute(
                'SELECT ip,`in-link-num` FROM bobstatus WHERE ip=%s', (bobIp,))
            result = cursor.fetchone()
            if result is None:
                print(f'Error: 更改in-link-num时找不到该{bobIp}')
                raise Exception('更改in-link-numh出错')
            cursor.execute(
                'UPDATE bobstatus SET `in-link-num`=%s WHERE ip=%s', (result[1] + 1, bobIp))

        # 在commit之前，UPDATE不会更改数据库（但是会增加AUTO_INCREMENT的值）
        connection.commit()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()
    global need_rollback_inLinkNum
    need_rollback_inLinkNum = True


def subtract_Bob_inLinkNum(link):
    '''
    为数据库里的Bob的参与链路数量减一
    '''
    need_reset_Bob = []
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        for bobIp in [i[1] for i in link]:
            cursor.execute(
                'SELECT ip,`in-link-num` FROM bobstatus WHERE ip=%s', (bobIp,))
            result = cursor.fetchone()
            if result is None:
                print(f'Error: 更改in-link-num时找不到该{bobIp}')
                raise Exception('更改in-link-numh出错')
            new_inLinkNum = result[1] - 1
            if new_inLinkNum < 0:
                print(f'Warning: {bobIp}参与链路数量为0')
            else:
                cursor.execute(
                    'UPDATE bobstatus SET `in-link-num`=%s WHERE ip=%s', (new_inLinkNum, bobIp))
            if new_inLinkNum == 0:
                need_reset_Bob.append(bobIp)

        connection.commit()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()

    # 重置inLinkNum减到0的Bob
    # for ip in need_reset_Bob:
    #     try:
    #         setBob_randomly(ip)
    #     except:
    #         # print(traceback.format_exc())
    #         print(f'Error: 重置{bobIp}的Bob失败')


def get_Bob_inLinkNum(bobIp):
    '''
    查找指定Bob的in-link-num值。
    若数据库里没有这个ip节点，也返回0
    '''
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute(
            'SELECT `in-link-num` FROM bobstatus WHERE ip=%s', (bobIp,))
        result = cursor.fetchone()

    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()

    if result != None:
        return result[0]
    else:
        # print('Note: 数据库bobstatus表中未找到该Bob的记录')
        return 0


def createLink(length: int, ip_or_country, targetType: int):
    '''
    创建一条链路，策略为只有出口节点为国外，其余为国内随机。
    length (int): 链路的长度（含多少个节点）
    ip_or_country (str): ip或国家
    返回描述链路的列表
    '''
    link = []
    # 选取国内的节点
    exit_ip = ip_or_country if targetType == 0 else None
    for i in range(length - 1):
        chooseNode(link, country_list['中国'], exit_ip)

    # 选取最后一个节点
    if isinstance(ip_or_country, str):  # 是ip
        link.append(['-1', ip_or_country, '-1'])
    elif isinstance(ip_or_country, int):  # 是country
        chooseNode(link, ip_or_country, exit_ip)

    add_Bob_inLinkNum(link)

    global need_rollback_port
    need_rollback_port = True
    try:
        # 从每个节点处申请一个空闲的端口号，作为Alice的端口号
        for i in range(length - 1):
            link[i][0] = mallocPort(link[i][1])
            link[i][2] = mallocPort(link[i][1])
        link[length - 1][0] = '0'
    except Exception as e:
        raise StoreRollbackDataException(link, e)

    return link


def freeLink(link):
    '''
    释放每个节点分配的端口
    '''
    for i in range(len(link) - 1):
        freePort(link[i][1], link[i][0])
        freePort(link[i][1], link[i][2])


def generateSSHConfig(ip):
    '''
    生成SSH的配置列表。
    '''
    if ip not in node_configs.keys():
        print(f'Error: 数据库中找不到{ip}的配置')
        raise ShowToUserException('节点不存在')
    return [
        ip,
        node_configs[ip][0],
        node_configs[ip][1],
        node_configs[ip][2],
    ]


# configs格式参考
# configs = [
#     [  # 需要向用户返回的东西
#         '152.136.175.162',  # 入口节点ip
#         '1082',  # 入口节点（Bob）端口号
#         '123456',  # 连接Bob的密码
#         '1081',  # 入口节点的Alice的端口号
#         'chacha20'
#     ],
#     [
#         # 前4个是远程控制Alice所在服务器所需要的参数
#         '152.136.175.162',
#         '22',
#         'root',
#         'ldKcTrC?g83)',
#         # Alice的参数
#         '1081',  # Alice在本地所监听的端口
#         '49.232.253.70',  # 下一跳（Bob）的ip
#         '1082',  # 下一跳（Bob）的端口
#         '123456',  # 下一跳连接Bob的密码
#         '1081',  # 下一个Alice所监听的端口
#         '1080',  # [9] http端口号
#         'chacha20'  # [10] 下一跳bob加密方式
#     ],
# ]
def generateAliceConfigs(link):
    '''
    生成Alice链（各个Alice的配置）
    '''
    configs = []
    for i in range(len(link) - 1):  # 最后一个节点没有Alice
        now_ip = link[i][1]
        next_ip = link[i + 1][1]
        if next_ip not in node_configs.keys():
            print(f'Error: {next_ip}节点不存在')
            raise ShowToUserException('节点不存在')
        config = generateSSHConfig(now_ip)
        config.extend([
            link[i][0],
            next_ip,
            node_configs[next_ip][3],
            node_configs[next_ip][4],
            link[i + 1][0],
            link[i][2],
            node_configs[next_ip][5]
        ])
        configs.append(config)

    first_ip = link[0][1]  # 入口节点ip
    if first_ip not in node_configs.keys():
        print(f'Error: {first_ip}节点不存在')
        raise ShowToUserException('节点不存在')
    configs.insert(0, [
        first_ip,
        node_configs[first_ip][3],
        node_configs[first_ip][4],
        link[0][0],
        node_configs[first_ip][5]
    ])
    return configs


def read_port_dict():
    global port_dict
    if not os.path.exists('./userlink/port_dict'):
        port_dict = {}
    else:
        with open('./userlink/port_dict', 'rb') as file:
            port_dict = pickle.load(file)


def write_port_dict():
    global port_dict
    if not os.path.exists('userlink'):
        os.makedirs('userlink')
    with open('./userlink/port_dict', 'wb') as file:
        pickle.dump(port_dict, file)
    # port_dict = None


def rollback_for_buildLink0(link):
    if link == None:
        return
    if need_rollback_Alice:
        destroyAlices(generateAliceConfigs(link))
    if need_rollback_port:
        freeLink(link)
        write_port_dict()
    if need_rollback_inLinkNum:
        subtract_Bob_inLinkNum(link)


def is_valid_ipv4(ip):
    # 定义 IPv4 地址的正则表达式
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'

    # 使用 re.match() 方法进行匹配
    match = re.match(pattern, ip)

    if not match:
        return False

    # 获取每个数值
    octet1, octet2, octet3, octet4 = map(int, match.groups())

    # 判断每个数值是否在合法范围内 (0 <= x <= 255)
    if 0 <= octet1 <= 255 and 0 <= octet2 <= 255 and 0 <= octet3 <= 255 and 0 <= octet4 <= 255:
        return True
    else:
        return False


def check_parameters_for_buildLink0(linkLength: int, targetType: int, target: str):
    if not isinstance(linkLength, int) or linkLength <= 0:
        raise ShowToUserException('参数错误：链路长度错误')
    if targetType != 0 and targetType != 1:
        raise ShowToUserException('参数错误：目标类型错误')
    if targetType == 0:
        if is_valid_ipv4(target) == False:
            raise ShowToUserException('参数错误：ip地址格式错误')
    elif targetType == 1:
        if target not in country_list.keys():
            raise ShowToUserException('参数错误：目标地区未定义')


def buildLink(username: str, linkLength: int, targetType: int, target: str):
    '''
    targetType：0为指定ip，1为国家。
    target：当为国家时，需要在country_list的键之中。
    username：需要所有用户唯一
    linkLength：链路长度。

    实现功能：
    国内随机跳，最后一跳跳到国外

    这是buildLink0的包装，负责记录链路文件，以及参数检查
    '''
    try:
        if ' ' in username:
            raise ShowToUserException('参数错误：用户名不应含有空格')

        client_Alice_config, link = buildLink0(linkLength, targetType, target)

        # 读取用户已有的链路数据
        if os.path.exists(f'./userlink/{username}.json'):
            with open(f'./userlink/{username}.json', 'r') as file:
                links = json.load(file)
        else:
            links = []

        # 写入链路
        links.append(link)
        if not os.path.exists('userlink'):
            os.makedirs('userlink')
        with open(f'./userlink/{username}.json', 'w') as file:
            json.dump(links, file)

        return client_Alice_config
    except Exception as e:
        print(traceback.format_exc())
        # 若是自定义异常，则抛出信息，返回给用户
        if isinstance(e, ShowToUserException):
            raise e
        else:
            raise Exception("查看控制台以获取更多信息")


'''
buildlink0的返回值，第一个列表未client_Alice_config，第二个列表为link

(
    [
        "81.70.154.58",  # 入口节点ip
        22544,  # 入口节点（Bob）端口号
        "Q6PNiE",  # 连接Bob的密码
        "18619",  # 入口节点的Alice的端口号
        "chacha20"  # 入口节点Bob的加密方式
    ],
    [
        [
            "18619",  # Alice所监听的端口
            "81.70.154.58",  # ip
            "14094"  # Alice的http端口
        ], 
        ["13823", "49.232.201.146", "27060"], ["0", "208.72.153.149", "-1"]
    ]
)
'''


def buildLink0(linkLength: int, targetType: int, target: str):
    '''
    targetType：0为指定ip，1为国家。
    target：当为国家时，需要在country_list的键之中。
    linkLength：链路长度。

    实现功能：
    国内随机跳，最后一跳跳到国外
    '''
    try:
        check_parameters_for_buildLink0(linkLength, targetType, target)

        global need_rollback_port, need_rollback_Alice, need_rollback_inLinkNum
        need_rollback_port = False
        need_rollback_Alice = False
        need_rollback_inLinkNum = False
        read_port_dict()
        read_country_ips()
        read_node_configs()

        if targetType == 0:
            ip_or_country = target
        elif targetType == 1:
            ip_or_country = country_list[target]

        # 生成链路，向每个节点分发Alice
        # 避免createLink中出异常，link未赋值，导致下面rollback_for_buildLink(link)出现link引用前未赋值错误
        link = None
        link = createLink(linkLength, ip_or_country, targetType)
        configs = generateAliceConfigs(link)
        createAlices(configs)

        write_port_dict()
        return configs[0], link
    except Exception as e:
        # 从StoreRollbackDataException中拆解出数据
        if isinstance(e, StoreRollbackDataException):
            link = e.link
            e = e.exception
        rollback_for_buildLink0(link)
        # 若是自定义异常，则抛出信息，返回给用户
        # if isinstance(e, ShowToUserException):
        #     raise e
        # else:
        #     raise Exception("查看控制台以获取更多信息")
        raise e


def read_user_links(username:str):
    """
    从文件中读取用户正在使用的链路
    """
    try:
        with open(f'./userlink/{username}.json', 'r') as file:
            links = json.load(file)
    except:
        raise ShowToUserException('打开用户链路文件失败，请检查文件是否存在')
    return links

def write_user_links(username:str,links:list):
    """
    写入用户链路文件
    """
    with open(f'./userlink/{username}.json', 'w') as file:
        json.dump(links, file)


def deleteLink(username: str, links_to_del=None):
    '''
    删除指定用户的链路。
    返回成功删除的数量
    links_to_del是后加的参数，支持仅删除用户的部分链路
    '''
    links = None
    linkId = None
    link_to_del = None
    ret = 0
    try:
        if ' ' in username:
            raise ShowToUserException('参数错误：用户名不应含有空格')

        read_node_configs()

        try:
            with open(f'./userlink/{username}.json', 'r') as file:
                links = json.load(file)
        except:
            raise ShowToUserException('打开用户链路文件失败，请检查文件是否存在')

        if links_to_del is None:
            for linkId in range(len(links)):
                link = links[linkId]
                deleteLink0(link)
                ret += 1
            os.remove(f'./userlink/{username}.json')
        else:
            # for link_to_del in links_to_del:
            #     links_that_remain = []
            #     for userlink in links:
            #         if userlink == link_to_del:
            #             deleteLink0(link_to_del)
            #             ret += 1
            #         else:
            #             links_that_remain.append(userlink)
            #     links = links_that_remain
            links_that_remain = []
            for userlink in links:
                if userlink in links_to_del:  # 这里in判断不知道会不会出问题
                    deleteLink0(userlink)
                    ret+=1
                else:
                    links_that_remain.append(userlink)
            links = links_that_remain
            with open(f'./userlink/{username}.json', 'w') as file:
                json.dump(links, file)
    except Exception as e:
        print(traceback.format_exc())
        if links_to_del is None:
            print('Warning: 出现异常，链路删除可能不完整，请再次执行删除该链路的操作')
            print('已成功删除的链路：', links[:linkId])

            # 写回链路
            links = links[linkId:]
            with open(f'./userlink/{username}.json', 'w') as file:
                json.dump(links, file)

            if isinstance(e, ShowToUserException):
                raise e
            else:
                raise Exception("查看控制台以获取更多信息")
        else:
            print('Warning: 出现异常，链路删除不完整')
            print('删除失败的链路为：', link_to_del)

    return ret


def deleteLink0(link: list):
    '''
    删除指定链路
    '''
    # 原实现
    # read_port_dict()
    # configs = generateAliceConfigs(link)  # 这一步实际上只需要用到4个ssh参数和config[4]Alice在本地监听的端口
    # destroyAlices(configs)
    # freeLink(link)
    # subtract_Bob_inLinkNum(link)
    # write_port_dict()

    invalid_ips=set()  # 失效ip集合
    unlived_node_set=getUnlivedNodeSet()

    read_port_dict()
    for node in link[:-1]:  # 最后一个节点没有Alice
        ip = node[1]
        # 跳过失效节点（因为失效节点已无法连接上，甚至可能数据库中已经没有该节点的记录了）
        if ip in unlived_node_set:
            invalid_ips.add(ip)
            continue
        config = generateSSHConfig(ip)
        config.extend([node[0]])
        destroy_Socks_Alice(config)
        freePort(ip, node[0])
        freePort(ip, node[2])
    subtract_Bob_inLinkNum([node for node in link if node[1] not in invalid_ips])
    write_port_dict()


def deleteLink_with_invalidNode(link: list, invalid_ip: str):
    """
    删除一个包含失效节点的链路
    """
    read_port_dict()
    for node in link[:-1]:  # 最后一个节点没有Alice
        ip = node[1]
        # 跳过失效节点（因为失效节点已无法连接上，甚至数据库中已经没有该节点的记录了）
        if ip == invalid_ip:
            continue
        config = generateSSHConfig(ip)
        config.extend([node[0]])
        destroy_Socks_Alice(config)
        freePort(ip, node[0])
        freePort(ip, node[2])
    subtract_Bob_inLinkNum([node for node in link if node[1] != invalid_ip])
    write_port_dict()


def isBobInLink(ip):
    '''
    判断Bob是否正在参与链路中
    '''
    inLinkNum = get_Bob_inLinkNum(ip)
    if inLinkNum != 0:
        return True
    return False


def closeBob_database(ip):
    '''
    将server表里live-flag设为0
    '''
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()

        # cursor.execute('DELETE FROM bobstatus WHERE ip=%s', (ip,))
        cursor.execute(
            'UPDATE server SET `live-flag`=0 WHERE serverip=%s', (ip,))

        connection.commit()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()


def closeBob(ip: str, forcedly=False):
    '''
    关闭指定Bob。
    就算该节点Bob不存在或未开启，不会报错终止。
    但有链路正在使用该Bob会阻止关闭Bob操作。
    若forcedly为True，则无视Bob是否在某条链路中，强制关闭。
    '''
    try:
        if not is_valid_ipv4(ip):
            raise ShowToUserException('参数错误：ip地址格式错误')

        if not forcedly and isBobInLink(ip):
            raise ShowToUserException('该Bob正在使用', 1)

        read_node_configs()

        if ip not in node_configs.keys():
            print(f'Warning: 关闭Bob时，数据库中找不到{ip}的SSH配置')
            # raise ShowToUserException('节点不存在')
            return

        # 释放Bob占用的端口
        if len(node_configs[ip]) != 6:  # 只有ssh配置，没有bob配置
            print(f'Note: 试图关闭一个不存在的Bob')
            return
        read_port_dict()
        freePort(ip, node_configs[ip][3])
        write_port_dict()

        # SSH连接，控制远程服务器关闭Bob
        sshconfig = generateSSHConfig(ip)
        destroy_Socks_Bob(sshconfig)

        closeBob_database(ip)

    except Exception as e:
        # print(traceback.format_exc())
        # print('Warning: Bob可能未完全关闭，可再次尝试执行该删除操作')
        if isinstance(e, ShowToUserException):
            raise e
        else:
            raise Exception("查看控制台以获取更多信息")


def check_parameters_for_setBob(ip: str, bob_port: str, bob_password: str, bob_encrypt_method: str):
    if not bob_port.isdigit():
        raise ShowToUserException('参数错误：Bob端口非数字')

    bob_port = int(bob_port)
    if bob_port < 10000 or bob_port > 30000:
        raise ShowToUserException('端口号范围应为10000-30000')


def rollback_for_setBob(ip: str, bob_port: str):
    if need_rollback_Bob_port:
        read_port_dict()
        freePort(ip, bob_port)
        write_port_dict()


def setBob_database(ip: str, bob_port: str, bob_password: str, bob_encrypt_method: str):
    '''
    Bob服务开启成功后，写数据库
    '''
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM bobstatus WHERE ip=%s', (ip,))
        if cursor.fetchone() != None:
            # print('Warning: 插入bobstatus表时发现ip已存在。进行覆盖')
            cursor.execute(
                'UPDATE bobstatus SET port=%s,password=%s,method=%s,`in-link-num`=0 WHERE ip=%s',
                (bob_port, bob_password, bob_encrypt_method, ip)
            )
        else:
            # 插入新的bobstatus记录
            cursor.execute(
                'INSERT INTO bobstatus (ip,port,password,method,`in-link-num`) VALUES (%s,%s,%s,%s,0)',
                (ip, bob_port, bob_password, bob_encrypt_method)
            )

        # 手动更新server表里的live-flag
        cursor.execute(
            'UPDATE server SET `live-flag`=1 WHERE serverip=%s', (ip,))

        connection.commit()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()


def setBob(ip: str, bob_port: str, bob_password: str, bob_encrypt_method: str):
    '''
    设置Bob，会覆盖原Bob。如果Bob正在使用则抛出异常
    '''
    try:
        check_parameters_for_setBob(
            ip, bob_port, bob_password, bob_encrypt_method)

        read_port_dict()
        # 记录该端口号为已使用
        if ip in port_dict:
            if bob_port in port_dict[ip]:
                raise ShowToUserException('该端口已被占用')
        else:
            port_dict[ip] = set()
        global need_rollback_Bob_port
        need_rollback_Bob_port = True
        port_dict[ip].add(int(bob_port))
        write_port_dict()

        # 尝试关闭Bob。该操作关闭Bob时也会更新port_dict
        closeBob(ip)

        # 覆盖地创建Bob
        read_node_configs()
        config = generateSSHConfig(ip)
        config.extend([
            bob_port,
            bob_password,
            bob_encrypt_method
        ])
        run_Socks_Bob(config)

        # 在数据库中更新Bob配置
        setBob_database(ip, bob_port, encrypt(
            bob_password), bob_encrypt_method)

    except Exception as e:
        # print(traceback.format_exc())
        # print('Warning: 原Bob可能已关闭')
        rollback_for_setBob(ip, bob_port)
        if isinstance(e, ShowToUserException):
            raise e
        else:
            raise Exception("查看控制台以获取更多信息")


def read_ips_inNodeconfig():
    '''
    从数据库nodeconfig表中读取所有ip
    '''
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()

        cursor.execute('SELECT ip FROM nodeconfig')
        result = cursor.fetchall()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        connection.close()
    result = [i[0] for i in result]
    return result


def getRandomPassword(length):
    characters = string.ascii_letters + string.digits  # 包含所有字母和数字的字符串
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


def getRandomBobMethod():
    return random.choice(bob_method_list)


def setBob_randomly(ip: str):
    '''
    随机参数地重置指定Bob。
    '''
    try:
        read_port_dict()  # 在setBob内有write_port_dict
        port = getUnusedPort(ip)
        password = getRandomPassword(6)
        method = getRandomBobMethod()
        setBob(ip, str(port), password, method)
        print(
            f'Bob重置成功：(ip={ip},port={port},password={password},method={method})')
    except Exception as e:
        # print(traceback.format_exc())
        if isinstance(e, ShowToUserException):
            raise e
        else:
            raise Exception("查看控制台以获取更多信息")


def resetAllBob() -> dict:
    '''
    从数据库nodeconfig表中找出所有ip，尝试重启其Bob。
    若一个Bob正在被某个链路使用，则跳过该Bob。

    返回字典，字典的键为未成功重启的Bob的ip（不包括Bob正在使用而引发的重启失败），值为失败的异常信息。
    这实际上是异常，因为不想中断整个重置过程，所以以返回值的形式给到外面。
    '''
    try:
        errors = {}
        ips = read_ips_inNodeconfig()
        for ip in ips:
            try:
                setBob_randomly(ip)
            except Exception as e:
                if isinstance(e, ShowToUserException) and e.type == 1:
                    print(f'Note: {ip}的Bob正在使用')
                else:
                    print(traceback.format_exc())
                    print(f'Error: {ip}的Bob重启失败，已跳过。异常信息：{str(e)}')
                    errors[ip] = str(e)
    except Exception as e:  # 这里捕获不了什么异常，只能捕获read_ips_inNodeconfig函数里的异常
        print(traceback.format_exc())
        if isinstance(e, ShowToUserException):
            raise e
        else:
            raise Exception("查看控制台以获取更多信息")

    return errors


def delete_Bob(ip):
    """
    删除bob
    """
    closeBob(ip, True)

    read_port_dict()
    try:
        port_dict.pop(ip)
    except KeyError:
        pass
    write_port_dict()

    config = generateSSHConfig(ip)
    path = '/root' if config[2] == 'root' else f'/home/{config[2]}'
    commands = [
        f'bash {path}/clear.sh \'{config[3]}\''
    ]
    run_commands_on_remote_host(config[0], int(config[1]), config[2], config[3], commands)


def buildSpecificLink(username):
    '''
    用于测试的函数，能够指定链路每个节点的ip，而不是随机选。这里面没怎么考虑异常处理
    '''
    length = 2
    ips = []
    ips.append('124.220.13.235')
    # ips.append('152.136.175.162')
    # ips.append('45.76.128.212')
    # ips.append('64.176.182.127')
    # ips.append('64.176.6.94')
    ips.append('208.167.255.248')
    # ips.append('207.148.71.45')

    if not os.path.exists('userlink'):
        os.makedirs('userlink')
    read_port_dict()
    read_country_ips()
    read_node_configs()

    # 手动设置每个节点的ip
    link = []
    for i in range(length - 1):
        link.append([mallocPort(ips[i]), ips[i], mallocPort(ips[i])])
    link.append(['0', ips[length - 1], '-1'])

    add_Bob_inLinkNum(link)

    configs = generateAliceConfigs(link)
    createAlices(configs)

    # 读取用户已有的链路数据
    if os.path.exists(f'./userlink/{username}.json'):
        with open(f'./userlink/{username}.json', 'r') as file:
            links = json.load(file)
    else:
        links = []
    # 写入链路
    links.append(link)
    with open(f'./userlink/{username}.json', 'w') as file:
        json.dump(links, file)

    write_port_dict()
    return configs[0]


def _show_port_dict():
    read_port_dict()
    print(port_dict)


def commandline():
    help_method = """method:
1. build
2. delete
3. showportdict
4. buildspecific
5. setBob
6. closeBob
7. resetAllBob
8. setBob_randomly"""
    print(help_method)
    method = input('method number: ')

    if method == '1':
        username = input('username: ')
        client_Alice_config = buildLink(username, 3, 1, '国外')
        print(client_Alice_config)
    elif method == '2':
        username = input('username: ')
        deleteLink(username)
    elif method == '3':
        _show_port_dict()
    elif method == '4':
        username = input('username: ')
        client_Alice_config = buildSpecificLink(username)
        print(client_Alice_config)
    elif method == '5':
        setBob('152.136.175.162', '10822', '654321', 'salsa20')
    elif method == '6':
        closeBob('152.136.175.162')
    elif method == '7':
        resetAllBob()
    elif method == '8':
        setBob_randomly('152.136.175.162')


if __name__ == '__main__':
    commandline()

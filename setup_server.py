import paramiko
import mysql.connector
import time
from router import setBob, setBob_randomly
from jiami import encrypt, decrypt
import threading
import traceback

zipPath = './setup_server/SocksAB.zip'
scriptPath = './setup_server/setup_server.sh'
script2Path = './setup_server/setup_server2.sh'

# runningIp = None  # 当前正在安装的服务器ip

db_config = {
    'user': 'root',
    'password': 'hitcs2020!',
    # 'host': '47.95.38.164',
    'host': '127.0.0.1',
    'database': 'heartbeat',
}


class BackgroundJobManager():
    def __init__(self) -> None:
        self.jobs = []
        self.do = False

    def addJob(self, func, args: tuple):
        self.jobs.append((func, args))
        # if len(self.jobs) == 1:  # 在这之前任务列表为空，即doJobs没有在运行
        threading.Thread(target=self.doJobs).start()

    def doJobs(self):
        if self.do:
            return
        else:
            self.do = True
        while len(self.jobs) > 0:
            func, args = self.jobs.pop(0)
            try:
                func(*args)
            except Exception as e:
                print(f'Error: 后台执行任务{func.__name__}{args}时遇到错误')
                print(traceback.format_exc())
        self.do = False


backgroundJobManager = BackgroundJobManager()


class ShowToUserException(Exception):
    '''
    展示给用户的异常信息
    '''
    pass


class SSH_Connector:
    def __init__(self, hostname, port, username, password) -> None:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(hostname, port=port,
                                username=username, password=password)
        except:
            raise ShowToUserException('SSH连接失败')

    def close(self) -> None:
        self.client.close()

    def run(self, command):
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            return stdout.read().decode(), stdout.channel.recv_exit_status()
        # except:
        #     raise ShowToUserException('运行远程指令失败')
        # except paramiko.SSHException:
        except:
            # print('运行远程指令终止')
            return None, 1

    def open_SFTP(self):
        self.sfpt = self.client.open_sftp()

    def close_SFTP(self):
        self.sfpt.close()

    def SFTP_put(self, local_file_path, remote_file_path):
        try:
            self.sfpt.put(local_file_path, remote_file_path)
        except:
            raise ShowToUserException('传输文件失败')


def setup_environment(hostname, port: int, username, password):
    '''
    远程操作，往服务器传文件，并执行.sh脚本
    参数port类型需要为int。
    '''
    print(f'Setting up for {hostname}...')

    connector = SSH_Connector(hostname, port, username, password)

    output, exit_status = connector.run('lsb_release -a')
    if 'Ubuntu 22' not in output:
        # print('Error: The version of Ubuntu is not 22.')
        connector.close()
        raise ShowToUserException('操作系统版本不为 Ubuntu 22')

    print('操作系统检查通过，开始传输文件')

    if username == 'root':
        remote_user_dir = '/root'
    else:
        remote_user_dir = f'/home/{username}'
    connector.open_SFTP()
    # 目标路径最后一定要加文件名，这与在控制台中用sftp的方式不同
    connector.SFTP_put(zipPath, remote_user_dir + '/SocksAB.zip')
    connector.SFTP_put(scriptPath, remote_user_dir + '/setup_server.sh')
    connector.SFTP_put(script2Path, remote_user_dir + '/setup_server2.sh')
    connector.close_SFTP()

    print('传输文件成功，开始执行setup_server.sh脚本')

    output, exit_status = connector.run(
        f'bash {remote_user_dir}/setup_server.sh \'{password}\'')
    # 检查执行.sh脚本结束后返回的状态码
    if exit_status == 1:
        # print('Error: apt or pip installation failed.')
        connector.close()
        raise ShowToUserException('apt或pip安装失败，请检查网络')

    print('setup_server.sh脚本执行成功。开始执行setup_server2.sh脚本。')

    # exec_command是阻塞的。不知道断开ssh连接后多久会返回
    connector.run(f'bash {remote_user_dir}/setup_server2.sh \'{password}\'')

    print('setup_server2.sh脚本执行结束。')

    connector.close()


def check_database(ip):
    query = "SELECT id FROM server WHERE serverip = %s AND `live-flag` = 1 AND TIMESTAMPDIFF(SECOND, `update-time`, NOW()) < 20"
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()

        cursor.execute(query, (ip,))
        rows = cursor.fetchall()
        # 如果找到了这样的结果，则返回True
        if rows:
            ret = True
        else:
            ret = False
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        cnx.close()
    return ret


def insertSSHConfigToDatabase(ip, port: int, username, password):
    '''
    往数据库nodeconfig中插入ssh的配置。
    '''
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()
        cursor.execute('SELECT * FROM nodeconfig WHERE ip=%s', (ip,))
        if cursor.fetchone() != None:  # 覆盖安装
            print('Warning: 数据库中已有该节点配置，进行覆盖')
            cursor.execute('DELETE FROM nodeconfig WHERE ip=%s', (ip,))
        cursor.execute(
            "INSERT INTO nodeconfig (ip,port,username,password) VALUES (%s,%s,%s,%s)",
            (ip, str(port), username, password)
        )
        cnx.commit()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        cnx.close()


def updateSSHConfigToNewPort(ip: str, port: int):
    '''
    更新数据库中的ssh端口为指定端口
    '''
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()
        cursor.execute('UPDATE nodeconfig SET port=%s WHERE ip=%s', (port, ip))
        cnx.commit()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        cnx.close()


def setup_server0(ip, bob_port: int, bob_password, bob_encrypt_method, shouldRandom: bool = False):
    try:
        global runningIp
        runningIp = ip
        port, username, password = read_SSHConfig(ip)
        setup_environment(ip, port, username, password)
        updateSSHConfigToNewPort(ip, 2222)
        if shouldRandom:
            setBob_randomly(ip)
        else:
            setBob(ip, str(bob_port), bob_password, bob_encrypt_method)

        print('Set up server successfully!')
        runningIp = None
    except Exception as e:
        # print(traceback.format_exc())
        if isinstance(e, ShowToUserException):
            raise e
        else:
            raise Exception('检查控制台已获取更多信息')


def setup_server(ip, bob_port: int, bob_password, bob_encrypt_method, shouldRandom: bool = False):
    # if runningIp is None:
    #     threading.Thread(target=setup_server0, args=(
    #         ip, bob_port, bob_password, bob_encrypt_method, shouldRandom)).start()
    # else:
    #     raise ShowToUserException(f'正在为{runningIp}执行安装程序，请稍后再试。')
    backgroundJobManager.addJob(setup_server0, args=(ip, bob_port, bob_password, bob_encrypt_method, shouldRandom))


def read_SSHConfig(ip: str):
    '''
    从数据库读指定ip的ssh配置
    返回顺序：port, username, password
    '''
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor()
        cursor.execute(
            'SELECT port,username,password FROM nodeconfig WHERE ip=%s', (ip,))
        result = cursor.fetchone()
    except:
        raise ShowToUserException('连接或操作数据库失败')
    finally:
        cursor.close()
        cnx.close()
    if result == None:
        raise ShowToUserException('数据库中没有该节点的ssh配置')
    # port, username, password
    return int(result[0]), result[1], decrypt(result[2])


if __name__ == "__main__":
    # insertSSHConfigToDatabase('207.148.71.45',22,'root',r't8@WEp_dEEXs*e4R')
    # setup_server('45.76.128.212',1082,'123456','chacha20')
    setup_server('49.232.253.70', 10826, '654321', 'salsa20')
    setup_server('152.136.175.162', 10827, '654321', 'salsa20')
    setup_server('110.42.209.65', 10828, '654321', 'salsa20')
    setup_server('124.221.221.133', 10829, '654321', 'salsa20')
    setup_server('45.76.128.212', 10830, '654321', 'salsa20')
    setup_server('64.176.182.127', 10831, '654321', 'salsa20')
    setup_server('64.176.6.94', 10832, '654321', 'salsa20')

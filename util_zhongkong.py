'''
为了防止zhongkong.py过长。
'''
import mysql.connector.pooling
import json
from datetime import datetime


class InfoException(Exception):
    '''
    能够记录一些信息的异常。主要以异常的方式传递信息
    '''

    def __init__(self, msg, info=None) -> None:
        '''
        info由异常抛出方和接受方约定
        '''
        super().__init__(msg)
        self.info = info


def get_subscription_userlist(connection, subscriptionName) -> list:
    '''
    从数据库service表里获取指定service-name的userlist列。
    若订阅不存在则返回None
    '''
    try:
        cursor = connection.cursor()
        cursor.execute(
            'SELECT userlist FROM subscription WHERE `subscription-name`=%s', (subscriptionName,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        if result == None:
            # raise InfoException('查询结果为空', 0)
            return None
        return eval(result[0])
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        cursor.close()
        connection.close()
        raise InfoException('查询出错', 1)


def set_subscription_userlist(connection, subscriptionName, newUserlist):
    """
    设置service表里指定service-name的userlist列。
    若订阅不存在则警告异常。
    """
    try:
        cursor = connection.cursor()
        cursor.execute(
            'UPDATE subscription SET userlist=%s WHERE `subscription-name`=%s',
            (json.dumps(newUserlist), subscriptionName)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("Data inserted successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('插入错误')


def write_userlist(connection, username: str, passwd: str, phone: str, department: str,
                   grade: int):
    '''
    写数据库的userlist表
    '''
    try:
        cursor = connection.cursor()
        cursor.execute(
            'INSERT INTO userlist (username,passwd,phone,department,grade) VALUES (%s,%s,%s,%s,%s)',
            (username, passwd, phone, department, grade)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("Data inserted successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('插入错误')


def insert_subscription(connection, subscriptionName):
    '''
    往数据库subscription表里插入一条数据
    '''
    try:
        cursor = connection.cursor()
        cursor.execute(
            'INSERT INTO subscription (`subscription-name`,userlist) VALUES (%s,"[]")',
            (subscriptionName,)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("Data inserted successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('插入错误')


def delete_subscription(connection, subscriptionName):
    '''
    从数据库删除订阅
    '''
    try:
        cursor = connection.cursor()
        cursor.execute(
            'DELETE FROM subscription WHERE `subscription-name`=%s',
            (subscriptionName,)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("Data inserted successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('删除错误')


def insert_linknodelist(connection, node_name, servicer, ip, bandwidth, country, country_flag: int):
    '''
    往数据库subscription表里插入一条数据
    '''
    try:
        cursor = connection.cursor()
        cursor.execute(
            'INSERT INTO linknodelist (`node-name`,servicer,ip,bandwidth,country,`country-flag`) VALUES (%s,%s,%s,%s,%s,%s)',
            (node_name, servicer, ip, bandwidth, country, country_flag)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("Data inserted successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('插入错误')


def addUserPermission(connection, userList: list, subscriptionList: list):
    for subscriptionName in subscriptionList:
        oldUserList = get_subscription_userlist(connection, subscriptionName)
        set_subscription_userlist(connection, subscriptionName, list(set(oldUserList) | set(userList)))


def removeUserPermission(connection, userList: list, subscriptionList: list):
    for subscriptionName in subscriptionList:
        oldUserList = get_subscription_userlist(connection, subscriptionName)
        set_subscription_userlist(connection, subscriptionName, list(set(oldUserList) - set(userList)))


def get_used_links_count(connection, userName):
    """
    查询数据库的userlist表中的used-links-count。
    若为空则返回0。
    """
    try:
        cursor = connection.cursor()
        cursor.execute(
            'SELECT `used-links-count` FROM userlist WHERE `username`=%s', (userName,))
        result = cursor.fetchone()
        if result == None:
            # raise InfoException('用户不存在', 0)
            print('Error: 用户不存在')
            ret = None
        else:
            used_links_count = result[0]
            if used_links_count is None:
                used_links_count = 0
            ret = used_links_count

        cursor.close()
        connection.close()
        return ret
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        cursor.close()
        connection.close()
        raise InfoException('查询出错', 1)


def set_used_links_count(connection, userName, num):
    """
    为数据库的userlist表中的used-links-count设置值
    """
    try:
        cursor = connection.cursor()
        # cursor.execute(
        #     'UPDATE `used-links-count` FROM userlist WHERE `username`=%s', (userName,))
        cursor.execute(
            'UPDATE userlist SET `used-links-count`=%s WHERE `username`=%s',
            (num, userName)
        )

        connection.commit()
        cursor.close()
        connection.close()
        print("Data updated successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('更新出错')


def add_used_links_count(connection1, connection2, userName, num):
    """
    为数据库的userlist表中的used-links-count加上num。
    num可以为负数。
    connection需要两个，一个查询，一个更改。
    """
    old_used_links_count = get_used_links_count(connection1, userName)
    if old_used_links_count is None:
        raise InfoException('用户不存在', 0)
    new_used_links_count = old_used_links_count + num
    set_used_links_count(connection2, userName, new_used_links_count)


def delete_node_in_database(connection, ip):
    """
    在数据库中删除一个ip的相关信息。
    具体从bobstatus, linknodelist, nodeconfig, server四个表里删除
    """
    try:
        cursor = connection.cursor()
        cursor.execute(
            'DELETE FROM bobstatus WHERE `ip`=%s',
            (ip,)
        )
        cursor.execute(
            'DELETE FROM linknodelist WHERE `ip`=%s',
            (ip,)
        )
        cursor.execute(
            'DELETE FROM nodeconfig WHERE `ip`=%s',
            (ip,)
        )
        cursor.execute(
            'DELETE FROM server WHERE `serverip`=%s',
            (ip,)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("Data deleted successfully!")
    except mysql.connector.Error as error:
        print("Error executing query: {}".format(error))
        connection.rollback()
        cursor.close()
        connection.close()
        raise InfoException('删除错误')


def _main_with_databaseConnection():
    '''
    调试代码
    '''
    db_config = {
        'host': '47.95.38.164',
        # 'host': '127.0.0.1',
        'user': 'root',
        'password': 'hitcs2020!',
        'database': 'heartbeat',
    }
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="main_pool", pool_size=3, **db_config)
    # insert_subscription(connection_pool.get_connection(), 'subscription1')
    # delete_subscription(connection_pool.get_connection(), 'subscription1')
    # set_subscription_userlist(connection_pool.get_connection(), 'server4', ['admin', 'user1', 'user2'])
    # addUserPermission(connection_pool.get_connection(), ['user3', 'user4'], ['server4'])
    # print(get_used_links_count(connection_pool.get_connection(), 'admin'))
    add_used_links_count(connection_pool.get_connection(), connection_pool.get_connection(), 'admin', -101)


if __name__ == '__main__':
    _main_with_databaseConnection()

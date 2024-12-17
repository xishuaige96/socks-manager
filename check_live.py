'''
crontab内每分钟触发：* * * * * python3 /path/check_live.py
'''

import mysql.connector
from mysql.connector import Error
from bob import delete_link_with_invalid_node

# 数据库连接参数
config = {
    'user': 'root',
    'password': 'hitcs2020!',
    # 'host': '47.95.38.164',
    'host': '127.0.0.1',
    'database': 'heartbeat',
}

# 数据库查询语句
query = "SELECT id, serverip, `update-time` FROM server WHERE TIMESTAMPDIFF(MINUTE, `update-time`, NOW()) > 1"

# 数据库更新语句
update_query = "UPDATE server SET `live-flag` = 0 WHERE id = %s"


if __name__ == '__main__':
    invalid_ips=set()
    try:
        # 创建数据库连接
        cnx = mysql.connector.connect(**config)

        # 创建游标对象
        cursor = cnx.cursor()

        # 执行查询
        cursor.execute(query)

        # 获取查询结果
        rows = cursor.fetchall()

        # 如果查询结果不为空
        if rows:
            for row in rows:
                # 获取id和update_time
                id,ip, update_time = row
                invalid_ips.add(ip)
                # 检查update_time是否在1分钟前
                cursor.execute(update_query, (id,))

        # 提交事务，实现数据更新
        cnx.commit()

    except Error as e:
        print(f"An error occurred: {e}")
    finally:
        # 关闭游标和连接
        cursor.close()
        cnx.close()

    delete_link_with_invalid_node(invalid_ips)

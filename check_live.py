import time
import mysql.connector
from datetime import datetime, timedelta
import os
import json
from link_pool import allocateForLinkMethod
from router import deleteLink0


db_config = {
    'user': 'root',
    'password': 'hitcs2020!',
    'host': '127.0.0.1',
    'database': 'heartbeat',
    'pool_name': 'mypool',
    'pool_size': 20
}
connection_pool = mysql.connector.pooling.MySQLConnectionPool(**db_config)


def scan_and_modify(directory, target_ip):
    results = {}

    for group_name in os.listdir(directory):
        group_path = os.path.join(directory, group_name)
        if os.path.isdir(group_path):
            results[group_name] = {}

            for json_file in os.listdir(group_path):
                if json_file.endswith('.json'):
                    json_path = os.path.join(group_path, json_file)

                    with open(json_path, 'r') as file:
                        data = json.load(file)

                    delete_link_list = []
                    new_data = []

                    for entry in data:
                        is_delete = False
                        for link in entry['link']:
                            if link[0] == target_ip:
                                print("Found link: ", link)
                                deleteLink0(entry['link'])
                                print("Deleted link: ", entry['link'])
                                delete_link_list.append(entry['link'])
                                is_delete = True
                                break
                        if not is_delete:
                            new_data.append(entry)

                    deleted_count = len(delete_link_list)

                    if deleted_count > 0:
                        with open(json_path, 'w', encoding='utf-8') as file:
                            json.dump(new_data, file, ensure_ascii=False)
                        results[group_name][json_file.strip(".json")] = deleted_count

    for i in results:
        for j in results[i]:
            print(f"Allocating {results[i][j]} links in {i}/{j}")
            allocateForLinkMethod(i, j, results[i][j])
            print(f"Allocated {results[i][j]} links in {i}/{j}")


def update_live_flag():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()

        current_time = datetime.now()

        query = "SELECT serverip, `update-time` FROM server WHERE `live-flag` = 1"
        cursor.execute(query)
        servers = cursor.fetchall()
        servers_unlive = []
        for server in servers:
            serverip, update_time = server
            if isinstance(update_time, datetime):
                update_time = update_time
            else:
                update_time = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')

            if current_time - update_time > timedelta(minutes=30):
                update_query = "UPDATE server SET `live-flag` = 0 WHERE serverip = %s"
                cursor.execute(update_query, (serverip,))
                conn.commit()
                print(f"Updated live_flag to 0 for serverip: {serverip}")
                servers_unlive.append(serverip)

        return servers_unlive
    except mysql.connector.Error as err:
        print(f"Error: {err}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    local_path = os.path.dirname(os.path.abspath(__file__))
    try:
        while True:
            servers_unlive = update_live_flag()
            for serverip in servers_unlive:
                scan_and_modify(f'{local_path}/linkpool', serverip)
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping the script...")

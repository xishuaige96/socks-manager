'''
负责提前创建链路
'''
from jiami import decrypt, encrypt
import json
import os
from router import buildLink0, deleteLink0, read_node_configs, ShowToUserException
import threading
import shutil
import traceback
from typing import Callable

initialLinkNum = 5  # 初始为每个链路方法分配的链路数


class BackgroundJobManager():
    def __init__(self) -> None:
        self.jobs = []
        self.do = False

    def addJob(self, func: Callable, args: tuple):
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


def allocateForLinkMethod(subscriptionName: str, linkMethodId: str, linkNum: int):
    '''
    为一个链路方法分配链路，插在队尾。

    参数：
    subscriptionName和linkMethodId用于唯一标识该链路方法。
    targetType, target, linkLength为创建链路所需参数。
    linkNum为需要添加的链路数量。链路会添加在列表（队列）末尾。
    '''
    # 读取原来的链路池
    links = read_linkPool(subscriptionName, linkMethodId)

    # 分配链路
    targetType, target, linkLength = read_linkMethodConfig(
        subscriptionName, linkMethodId)
    for i in range(linkNum):
        try:
            client_Alice_config, link = buildLink0(
                linkLength, targetType, target)
        except Exception as e:
            print(
                f'Error: Exception occurs while building link. Only {i} built, expect {linkNum}')
            print(traceback.format_exc())
            write_linkPool(subscriptionName, linkMethodId, links)
            # 线程如果抛出异常，由谁、何时来捕获？
            # raise e
            return
        links.append(
            {'client_Alice_config': client_Alice_config, 'link': link})
        # print(f'成功为链路方法{subscriptionName}-{linkMethodId}分配了1条链路')

    # 写回新的链路池
    write_linkPool(subscriptionName, linkMethodId, links)
    print(f'成功为链路方法{subscriptionName}-{linkMethodId}分配了{linkNum}条链路')


def dequeueFromLinkMethod(subscriptionName: str, linkMethodId: str, linkNum: int, shouldDelete=False) -> list:
    '''
    从一个链路方法删除一个链路，并返回它的client_Alice_config。
    subscriptionName和linkMethodId用于唯一标识该链路方法。
    linkNum为需要删除的链路数量。链路会从队首开始删。linkNum为-1时表示删除所有链路

    返回list，list里面是一个个tuple，tuple里面是client_Alice_config和link。
    '''
    links = read_linkPool(subscriptionName, linkMethodId)

    ret = []

    if shouldDelete:
        read_node_configs()

    i = 0
    if linkNum == -1:
        linkNum = len(links)
    for i in range(linkNum):
        try:
            client_Alice_config = links[i]['client_Alice_config']
            link = links[i]['link']
            if shouldDelete:
                deleteLink0(link)
            ret.append((client_Alice_config, link))
        except Exception as e:
            print(f'Warning: 从链路方法中出队链路时出现异常。成功出队{i}/{linkNum}条链路。')
            links = links[i:]
            write_linkPool(subscriptionName, linkMethodId, links)
            raise e
            # 如果异常出现，则没有返回值

    links = links[i + 1:]
    write_linkPool(subscriptionName, linkMethodId, links)

    return ret


def read_subscriptionConfig(subscriptionName: str):
    '''
    读取订阅的配置
    '''
    with open(f'/opt/{subscriptionName}.json', 'r') as f:
        jsonStr = f.read()
        jsonStr = decrypt(jsonStr)
        linkMethods = json.loads(jsonStr)
        return linkMethods['data']


def read_linkMethodConfig(subscriptionName: str, linkMethodId: str):
    '''
    读取链路方法的配置
    '''
    linkMethods = read_subscriptionConfig(subscriptionName)
    linkMethod = linkMethods[int(linkMethodId)]
    return linkMethod['targetType'], linkMethod['target'], linkMethod['linkLength']


def getLink(subscriptionName: str, linkMethodId: str, username: str):
    '''
    从一个链路方法中获取一条链路。

    该链路会从资源池删除，并转移到<username>.json文件中进行维护。后续该资源池会自动补充一条新链路。
    '''
    # 读取用户链路文件
    if os.path.exists(f'./userlink/{username}.json'):
        with open(f'./userlink/{username}.json', 'r') as file:
            userlinks = json.load(file)
    else:
        userlinks = []

    # 从链路池取一条链路出队
    configAndLinks = dequeueFromLinkMethod(subscriptionName, linkMethodId, 1)
    if len(configAndLinks) == 0:
        raise ShowToUserException('链路池为空')
    client_Alice_config, link = configAndLinks[0]
    userlinks.append(link)

    # 写入用户链路
    if not os.path.exists('userlink'):
        os.makedirs('userlink')
    with open(f'./userlink/{username}.json', 'w') as file:
        json.dump(userlinks, file)

    # 异步地补充一条链路
    # thread = threading.Thread(target=allocateForLinkMethod, args=(
    #     subscriptionName, linkMethodId, 1))
    # thread.start()
    backgroundJobManager.addJob(
        allocateForLinkMethod, (subscriptionName, linkMethodId, 1))

    # 返回客户端Alice需要的配置
    return client_Alice_config


# subscription样例
# subscription={
#     'subscriptionName':'server1',
#     "data": [
#         {
#             "types": "动态随机",
#             "name": "动态随机链路1",
#             "encryption": "chacha20",
#             "mask": "单一伪装",
#             "targetType": 1,
#             "target": "foreign",
#             "linkLength": 2
#         },
#         {
#             "types": "动态随机",
#             "name": "动态随机链路2",
#             "encryption": "chacha20",
#             "mask": "混合伪装",
#             "targetType": 1,
#             "target": "foreign",
#             "linkLength": 3
#         },
#         {
#             "types": "动态随机",
#             "name": "动态随机链路3",
#             "encryption": "chacha20",
#             "mask": "混合伪装",
#             "targetType": 1,
#             "target": "China",
#             "linkLength": 3
#         }
#     ]
# }
def onSubscriptionCreated(subscriptionName: str):
    '''
    创建订阅时，预分配链路。

    内部涉及到为链路池分配链路，这需要/opt下已写入<subscriptionName>.json！
    '''
    if not os.path.exists('linkpool'):
        os.makedirs('linkpool')

    os.makedirs(f'./linkpool/{subscriptionName}')

    # thread=threading.Thread(target=allocateForSubscription,args=(subscriptionName,))
    # thread.start()
    backgroundJobManager.addJob(allocateForSubscription, (subscriptionName,))


def allocateForSubscription(subscriptionName: str):
    subscriptionData = read_subscriptionConfig(subscriptionName)

    for i in range(len(subscriptionData)):
        linkMethodId = str(i)
        linkNum = initialLinkNum

        allocateForLinkMethod(subscriptionName, linkMethodId, linkNum)


def read_linkPool(subscriptionName: str, linkMethodId: str) -> list:
    '''
    读取一个链路方法的链路池文件。读不到会返回空列表
    '''
    if os.path.exists(f'./linkpool/{subscriptionName}/{linkMethodId}.json'):
        with open(f'./linkpool/{subscriptionName}/{linkMethodId}.json', 'r') as file:
            links = json.load(file)
    else:
        links = []
    return links


def write_linkPool(subscriptionName: str, linkMethodId: str, links):
    '''
    读取一个链路方法的链路池文件。
    '''
    with open(f'./linkpool/{subscriptionName}/{linkMethodId}.json', 'w') as file:
        json.dump(links, file)


def deleteAllLinkFromSubsciption(subscriptionName: str):
    '''
    删除一个订阅中的所有链路。删除该订阅链路池文件夹。

    还包括删除/opt下的订阅文件
    '''
    linkMethods = read_subscriptionConfig(subscriptionName)
    for i in range(len(linkMethods)):
        try:
            dequeueFromLinkMethod(subscriptionName, str(i), -1, True)
            os.remove(f'./linkpool/{subscriptionName}/{str(i)}.json')
        except Exception as e:
            print(
                f'Error: 删除订阅的链路池时出现异常。已成功删除{i}/{len(linkMethods)}个链路方法。可尝试再次执行该函数。')
            # 线程如果抛出异常，由谁、何时来捕获？
            raise e
    shutil.rmtree(f'./linkpool/{subscriptionName}')
    print('删除订阅的所有链路池成功')
    os.remove(f'/opt/{subscriptionName}.json')
    print('删除订阅文件成功')


def onSubscriptionDeleted(subscriptionName: str):
    '''
    删除订阅后，删除该订阅下的所有链路方法的所有链路。
    '''
    # thread=threading.Thread(target=deleteAllLinkFromSubsciption,args=(subscriptionName,))
    # thread.start()
    backgroundJobManager.addJob(
        deleteAllLinkFromSubsciption, (subscriptionName,))


def commandline():
    menu = """command menu:
1. onSubscriptionCreated
2. getLink
3. onSubscriptionDeleted
command number: """
    print(menu, end='')
    command = input()
    if command == '1':
        # 测试前请确保服务器/opt目录下有testlinkpoolserver.json文件，源文件在./test目录下
        onSubscriptionCreated('testlinkpoolserver')
    elif command == '2':
        subscriptionName, linkMethodId, username = input(
            '<subscriptionName> <linkMethodId> <username>: ').split(' ')
        client_Alice_config = getLink(subscriptionName, linkMethodId, username)
        print(client_Alice_config)
    elif command == '3':
        subscriptionName = input('<subscriptionName>: ')
        onSubscriptionDeleted(subscriptionName)


if __name__ == '__main__':
    commandline()

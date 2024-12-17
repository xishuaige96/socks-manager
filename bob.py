from link_pool import read_linkPool,write_linkPool,allocateForLinkMethod
from router import read_node_configs,deleteLink0,read_user_links,write_user_links
import os

def delete_link_with_invalid_node(nodeips:set):
    """
    删除包含失效节点的链路。
    当前为仅从链路池中删除。
    """
    read_node_configs()

    # 从链路池中找
    subscriptionNames=os.listdir('./linkpool/')
    for subscriptionName in subscriptionNames:
        filenames=os.listdir(f'./linkpool/{subscriptionName}/')
        linkMethodIds=[filename[:-5] for filename in filenames]
        for linkMethodId in linkMethodIds:
            links_with_clientAliceConfig=read_linkPool(subscriptionName, linkMethodId)
            deletedNum=0  # 以删除的链路数，用于后续补充链路
            links_with_clientAliceConfig_that_remain=[]
            for i in range(len(links_with_clientAliceConfig)):
                link=links_with_clientAliceConfig[i]['link']
                # if nodeip in [node[1] for node in link]:  # 该链路中包含失效节点
                if not nodeips.isdisjoint(set([node[i] for node in link])):  # 判断两个集合是否有交集，有交集则表明该链路中包含失效节点
                    deleteLink0(link)
                    # deleteLink_with_invalidNode(link,nodeip)
                    deletedNum+=1
                else:
                    links_with_clientAliceConfig_that_remain.append(links_with_clientAliceConfig[i])
            write_linkPool(subscriptionName,linkMethodId,links_with_clientAliceConfig_that_remain)
            if deletedNum!=0:
                allocateForLinkMethod(subscriptionName,linkMethodId,deletedNum)

    # 从用户正在使用列表中找
    usernames=os.listdir('./userlink/')
    usernames=[username[:-5] for username in usernames if username!='port_dict']
    for username in usernames:
        userlinks=read_user_links(username)
        userlinks_that_remain=[]
        for userlink in userlinks:
            if not nodeips.isdisjoint(set([node[1] for node in userlink])):
                deleteLink0(userlink)
            else:
                userlinks_that_remain.append(userlink)
        write_user_links(username,userlinks_that_remain)


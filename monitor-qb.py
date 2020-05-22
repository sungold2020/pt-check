#!/usr/bin/python3
# coding=utf-8
import os
#import re
#import sys
#import shutil
import datetime
import time
#from pathlib import Path
import qbittorrentapi 
import psutil

"""
安装和使用说明
一、安装:
1、python3
脚本基于python3，所以前提是要安装python3：
apt-get install python3
apt-get install pip3
2、安装qbittorrent-api(qbittorent的python一个api模块)
pip3 install qbittorrentapi

二、配置
配置比较简单都写在脚本里了，你可以自行修改，必须修改的只有第一项
1、QB的web-ui相关配置，包括端口号，用户和密码，这个必须配置
2、关闭和重启QB之间的休眠时间（给缓存写入磁盘留够时间），缺省600秒
3、内存占比超过阀值后，重启QB，缺省95%
4、检测间隔时间，缺省600秒
5、重启qbittorrent的命令行，不同linux环境会有不同，需要根据自己的情况来修改，缺省的适用于我的ubuntu环境
   注意：我的ubuntu桌面版，qbittorrent需要启动客户端，远程环境需要设置DISPLAY才能成功。不知道怎么操作的就在ubuntu本机桌面的"终端"中运行该脚本。
   
三、运行
1、增加该脚本的执行权限
chmod +x monitor-qb.py
2、运行该脚本
monitor-qb.py &
"""
# qbittorrent的相关配置
QB_IPPORT = 'localhost:8989'  #IP和端口号（脚本运行在本机，所以IP就填写localhost。）端口号填写你设定的端口号
QB_USER = 'admin'                  #用户名
QB_PWD =  'adminadmin'             #密码
    
def RestartQB():

    #连接到QB，暂停种子，并关闭QB
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        qb_client.torrents.pause.all()
        qb_client.app_shutdown()
    except:
        print("failed to stop QB")
        return False
    else:
        print("success to stop QB")
        
    #休眠10分钟，给qb后台完成缓存的写入时间，避免重启后重新校验
    time.sleep(600)
    
    #重启QB，执行命令行"/usr/bin/qbittorrent &"，适用于我的ubuntu环境，其他linux环境，请更换对应的命令行
    #   注意：我的ubuntu桌面版，qbittorrent需要启动客户端，远程环境需要设置DISPLAY才能成功。不知道怎么操作的就在ubuntu本机桌面的"终端"中运行该脚本。
    if os.system("/usr/bin/qbittorrent &") == 0 : print ("success to start qb")
    else : print("failed to start qb"); return False
    
    time.sleep(10)
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)
        qb_client.auth_log_in()
        qb_client.torrents.resume.all()
    except:
        print("failed to resume torrents")
        return False
    else: print("success to resume torrents")
    return True
    

   
if __name__ == '__main__' :

    while True:
        #检查一下内存占用
        tMem = psutil.virtual_memory()
        print("memory percent used:"+str(tMem.percent))
        if tMem.percent >= 75: #内存占比超过95%
            print("memory percent used:"+str(tMem.percent))
            RestartQB()
                
        #休眠10分钟后再检查
        time.sleep(600)
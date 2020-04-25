#!/usr/bin/python3
# coding=utf-8
import os
import datetime
import time
import requests
from bs4 import BeautifulSoup
import qbittorrentapi

QB_IPPORT = 'localhost:8989'               #QB的web-ui的端口号，用户和密码
QB_USER = 'admin'
QB_PWD =  'adminadmin'
MAXNUMBEROFRSS = 1000                      #最多保存RSS记录的条数
SLEEPTIME      = 600                       #RSS刷新间隔时间，单位秒

RSSBackupFile = "data/rss.txt"             #rss记录备份文件
DebugLogFile = "log/debug.rss"             #debug日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/error.rss"             #错误日志
ExecLogFile  = "log/exec.rss"              #执行日志

# 你的RSS订阅链接和名称，名称可以自己取，链接来自于网站
RSSList=[\
    {'Name':'HDXX', 'Url':'xxx'},\
    {'Name':'HDX2', 'Url':'xxx'}]

    
gRSSList = []  

def LogClear(FileName) :
    if os.path.isfile(FileName):
        if os.path.isfile(FileName+".old"):    os.remove(FileName+".old")
        os.rename(FileName,FileName+".old")
        
def Log(FileName,Str) :
    fo = open(FileName,"a+")
    tCurrentTime = datetime.datetime.now()
    fo.write(tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')+"::")
    fo.write(Str)
    fo.write('\n')
    fo.close()

def DebugLog( Str, Mode = "np"):    
    Log(DebugLogFile,Str)
    if Mode == "p": print(Str)

def ExecLog(Str):
    DebugLog(Str)
    Log(ExecLogFile,Str)
    
def ErrorLog(Str):
    print(Str)
    DebugLog(Str)
    Log(ErrorLogFile,Str)

class RSS:
    def __init__ (self,RSSName,ID,DownloadLink,Title,Downloaded='0'):
        self.RSSName = RSSName
        self.ID  = ID
        self.DownloadLink = DownloadLink 
        self.Title = Title              
        self.Downloaded = Downloaded   #'0'|'1'
        
def ReadRSSBackup():
    """
    读取备份目录下的rss.txt，用于恢复RSS记录数据，仅当初始化启动时调用
    """
    
    if not os.path.isfile(RSSBackupFile):
        DebugLog(RSSBackupFile+" does not exist")
        return 0
        
    for line in open(RSSBackupFile):
        RSSName,ID,DownloadLink,Downloaded,Title = line.split('|',4)
        if Title[-1:] == '\n' :  Title = Title[:-1]  #remove '\n'
        gRSSList.append(RSS(RSSName,ID,DownloadLink,Title,Downloaded))
    return 1

def WriteRSSBackup():
    """
    把当前RSS列表写入备份文件
    """
    
    LogClear(RSSBackupFile)        
    try :
        fo = open(RSSBackupFile,"w")
    except:
        ErrorLog("Error:open backup file to write："+RSSBackupFile)
        return -1
        
    i = 0; tLength = len(gRSSList)
    while i < tLength :
        tStr  =     gRSSList[i].RSSName+'|'
        tStr +=     gRSSList[i].ID+'|'
        tStr +=     gRSSList[i].Downloaded+'|'
        tStr +=     gRSSList[i].DownloadLink+'|'
        tStr +=     gRSSList[i].Title+'\n'
        fo.write(tStr)
        i += 1   
    fo.close()
    return 1


if __name__ == '__main__' :

    headers = {    
        'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.82 Safari/537.36'}

    #读取RSS备份文件
    if ReadRSSBackup() > 0 : ExecLog("成功读取RSS备份文件:"+RSSBackupFile)
    

    while True :
        try:
            qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
            qb_client.auth_log_in()
            ExecLog("connected to QB ")
        except:
            ExecLog("failed to connect QB ")
            time.sleep(100)
            continue
            
        IsUpdated = False       
        for tRSS in RSSList:
            RSSName = tRSS['Name']
            url     = tRSS['Url' ]

            ExecLog("==========begin {}==============".format(RSSName.ljust(10,' ')))
            try: page = requests.get(url, timeout=60, headers=headers)
            except: ExecLog("failed to requests:"+RSSName); continue 
            page.encoding = 'utf-8'
            page_content = page.text
            soup = BeautifulSoup(page_content, 'lxml-xml')
            items = soup.select('rss > channel > item')
            for i in range(len(items)):
                Title = items[i].title.string
                ID    = items[i].guid.string
                DownloadLink = items[i].enclosure.get('url')

                IsOld = False
                for tRSS in gRSSList:
                    if RSSName == tRSS.RSSName and ID == tRSS.ID : 
                        DebugLog("old rss, ignore it:"+Title)
                        IsOld = True
                        break
                if IsOld == True : continue
                
                IsUpdated = True
                ExecLog("new rss: "+Title)
                gRSSList.append(RSS(RSSName,ID,DownloadLink,Title))
                if len(gRSSList) > MAXNUMBEROFRSS : del gRSSList[0]
    
                #加入Torrents
                try: qb_client.torrents_add(urls=DownloadLink)
                except: ExecLog("failed to add torrent:"+Title); continue
                ExecLog("success add torrent:"+Title)
            #end for Items
        #end for RSSList

        if IsUpdated :
            if WriteRSSBackup() > 0 : ExecLog("成功备份RSS备份文件:"+RSSBackupFile)   
        
        ExecLog("begin sleep:")
        time.sleep(SLEEPTIME)



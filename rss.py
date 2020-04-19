#!/usr/bin/python3
# coding=utf-8
import os
import re
import sys
import shutil
import datetime
import time
#import mysql.connector
from pathlib import Path
import requests
import codecs 
from bs4 import BeautifulSoup
import feedparser
import qbittorrentapi

DownloadFolder = "/media/root/BT"
QB_IPPORT = 'localhost:8989'
QB_USER = 'admin'
QB_PWD =  ''


DebugLogFile = "log/debug.rss"             #日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/error.rss"             #错误日志
ExecLogFile  = "log/exec.rss"
RSSList=[\
    {'Name':'BeiTai',   'Url':'https://www.beitai.pt/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=&inclbookmarked=1'},\
    {'Name':'LeagueHD', 'Url':'https://leaguehd.com/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=d&inclbookmarked=1'},\
    {'Name':'HDHome',   'Url':'http://hdhome.org/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=9358&inclbookmarked=1'},\
    {'Name':'HDArea',   'Url':'https://www.hdarea.co/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=&inclbookmarked=1'},\
    {'Name':'JoyHD',    'Url':'https://www.joyhd.net/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=&inclbookmarked=1'},\
    {'Name':'SoulVoice','Url':'https://pt.soulvoice.club/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=&inclbookmarked=1'},\
    {'Name':'PTSBao',   'Url':'https://ptsbao.club/pushrss.php?pushkey='},\
    {'Name':'PTHome',   'Url':'http://pthome.net/torrentrss.php?myrss=1&linktype=dl&uid=116626&passkey='},\
    {'Name':'AVGV',     'Url':'http://avgv.cc/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=&inclbookmarked=1'},\
    {'Name':'FRDSAll',  'Url':'https://pt.keepfrds.com/torrentrss.php?rows=10&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=9'},\
    {'Name':'MTeam',    'Url':'https://pt.m-team.cc/torrentrss.php?https=1&rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=&inclbookmarked=1'}]


BeiTaiAll='https://www.beitai.pt/torrentrss.php?rows=50&icat=1&ismalldescr=1&isize=1&linktype=dl&passkey=e'


import mysql.connector
g_DB = mysql.connector.connect(
  host="localhost",      # 数据库主机地址
  user="dummy",    # 数据库用户名
  passwd="moonbeam" ,  # 数据库密码
  database=""
)
g_MyCursor = g_DB.cursor()

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

#url="https://movie.douban.com/subject/1298038/"
#url="https://www.imdb.com/title/tt0125439/"

headers = {    
    'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.82 Safari/537.36'}

while True :
    BTStat =  os.statvfs(DownloadFolder)
    FreeSize = (BTStat.f_bavail * BTStat.f_frsize) /(1024*1024*1024)
    ExecLog("free size:"+str(FreeSize))
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        ExecLog("connected to QB ")
    except:
        ExecLog("failed to connect QB ")
        time.sleep(100)
        continue

    for tRSS in RSSList:
        RSSName = tRSS['Name']
        url     = tRSS['Url' ]
        
        DebugLog("")
        ExecLog("==========begin "+RSSName+"  ==============")
        DebugLog(url)
        
        try:
            page = requests.get(url, timeout=10, headers=headers)
        except:
            ExecLog("failed to requests:"+RSSName)
            continue
            
        page.encoding = 'utf-8'
        page_content = page.text
        soup = BeautifulSoup(page_content, 'lxml-xml')
        items = soup.select('rss > channel > item')
        for i in range(len(items)):

            Title = items[i].title.string
            ID    = items[i].guid.string
            DownloadLink = items[i].enclosure.get('url')
            DoubanScore = ""
            DoubanLink = ""
            IMDBLink = ""
            IMDBScore = ""

            DebugLog(Title+":"+ID)
            DebugLog(DownloadLink)

            se_sql = "select Title from rss where RSSName=%s and ID=%s"
            se_val = (RSSName,ID)    
            g_MyCursor.execute(se_sql,se_val)
            tSelectResult = g_MyCursor.fetchall()
            if len(tSelectResult) > 0:
                DebugLog("old rss,ignore it:"+Title)
                continue

            if RSSName == "LeagueHD" or\
               RSSName == "JoyHD"    or\
               RSSName == "HDArea"   or\
               RSSName == "PTSBao"   or\
               RSSName == "BeiTai"   or\
               RSSName == "MTeam"    :
                SummaryStr = items[i].description.string
                SummaryStr.replace(u'\u3000',u' ')
                SummaryStr.replace(u'\xa0', u' ')
                SummaryStr.replace('&nbsp;',' ')
                SummaryStr = SummaryStr.lower()
                DebugLog(SummaryStr)
                        
                tIndex = SummaryStr.find("豆瓣评分")
                if tIndex >= 0 :
                    tempstr = SummaryStr[tIndex+5:tIndex+16]
                    tSearch = re.search("[0-9]\.[0-9]",tempstr)
                    if tSearch :
                        DoubanScore = tSearch.group()
                    else:
                        DoubanScore = ""
                    DebugLog("douban score:"+DoubanScore)
                else:
                    DebugLog("douban score:not find")
                
                tIndex = SummaryStr.find("豆瓣链接")
                if tIndex >= 0 :
                    tempstr = SummaryStr[tIndex:]
                    tIndex = tempstr.find("href=")
                    if tIndex >= 0:
                        tempstr = tempstr[tIndex+6:]
                        tIndex = tempstr.find('\"')
                        if tIndex >= 0 :
                            DoubanLink = tempstr[:tIndex]
                            DebugLog("douban link:"+DoubanLink)
                        else:
                            DebugLog("douban link:error:not find \"")
                    else:
                        DebugLog("douban link:error:not find href=")

                else:
                    DebugLog("douban link:not find")

                if   SummaryStr.find("imdb评分")    >= 0: tIndex = SummaryStr.find("imdb评分")           
                elif SummaryStr.find('imdb.rating') >= 0: tIndex = SummaryStr.find('imdb.rating')
                elif SummaryStr.find('imdb rating') >= 0: tIndex = SummaryStr.find('imdb rating')            
                else: tIndex = -1               
                if tIndex >= 0 :
                    tempstr = SummaryStr[tIndex+6:tIndex+36]
                    tSearch = re.search("[0-9]\.[0-9]",tempstr)
                    if tSearch :
                        IMDBScore = tSearch.group()              
                DebugLog("imdb score:"+IMDBScore)
                
                if   SummaryStr.find("imdb链接")    >= 0: tIndex = SummaryStr.find("imdb链接")
                elif SummaryStr.find('imdb.link')   >= 0: tIndex = SummaryStr.find("imdb.link")
                elif SummaryStr.find('imdb link')   >= 0: tIndex = SummaryStr.find("imdb link")
                elif SummaryStr.find('imdb url')    >= 0: tIndex = SummaryStr.find('idmb url')           
                else: tIndex = -1            
                if tIndex >= 0 :
                    tempstr = SummaryStr[tIndex:tIndex+200]
                    tIndex = tempstr.find("href=")
                    if tIndex >= 0:
                        tempstr = tempstr[tIndex+6:]
                        tIndex = tempstr.find('\"')
                        if tIndex >= 0 :
                            IMDBLink = tempstr[:tIndex]
                        else:
                            DebugLog("imdb link:error:not find \"")
                    else:
                        #DebugLog("imdb link:error:not find href=")  
                        tIndex = tempstr.find('http')
                        if tIndex >= 0:
                            tempstr = tempstr[tIndex:]
                            tIndex = tempstr.find('<')
                            if tIndex >= 0 :
                               IMDBLink = tempstr[:tIndex] 
                DebugLog("imdb link:"+IMDBLink)
            #end if RSSName ==
            
            ExecLog("new rss: "+Title)
            in_sql = "INSERT INTO rss \
                    (RSSName, ID, Title, DownloadLink, DoubanScore, DoubanLink, IMDBScore, IMDBLink) \
              VALUES(%s,      %s, %s   , %s          , %s         , %s        , %s       , %s )" 
            in_val= (RSSName, ID, Title, DownloadLink, DoubanScore, DoubanLink, IMDBScore, IMDBLink)
            DebugLog(RSSName)
            DebugLog(ID)
            DebugLog(Title)
            DebugLog(DownloadLink)
            DebugLog(DoubanScore)
            DebugLog(DoubanLink)
            DebugLog(IMDBScore)
            DebugLog(IMDBLink)
            try:
                g_MyCursor.execute(in_sql,in_val)
                g_DB.commit()
            except:
                ExecLog("insert error:"+Title)

                
            #加入Torrents
            try:
                qb_client.torrents_add(urls=DownloadLink,paused=True,category="temp")
            except:
                ExecLog("failed to add torrent:"+Title)
                continue
            ExecLog("success add torrent:"+Title)

            

        #end for Items
    #end for RSSList
        
    #torrents = qb_client.torrents_info(status_filter="paused",category="temp")
    torrents = qb_client.torrents_info(category="temp")
    for torrent in torrents:
        Size = torrent.total_size /(1024*1024*1024)
        DebugLog("Size:"+str(Size))
        if FreeSize < Size+1 :
            ExecLog("diskspace is not enough")
            break
        FreeSize -= Size
        torrent.resume()
        torrent.set_category(category="刷上传")
        ExecLog("start torrent:"+torrent.name)
        

        HASH = torrent.hash
        update_sql = "UPDATE rss set downloaded=1,TorrentName =%s where id=%s"
        update_val = (torrent.name,HASH)
        try:
            g_MyCursor.execute(update_sql,update_val)
            g_DB.commit()
        except:
            ExecLog("failed to update rss:"+RSSName+"::"+ID)
        ExecLog("success to update rss:"+torrent.name)

    ExecLog("begin sleep:")
    time.sleep(500)

            



    #print (d.feed.subtitle)
    #print (len(d.entries))
    #print (d.entries[0])

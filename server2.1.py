#!/usr/bin/python3
# coding=utf-8
import os
import re
import sys
import shutil
import datetime
import time
from pathlib import Path
import datetime
import qbittorrentapi 
import transmissionrpc
import psutil
import movie
import mysql.connector
from gen import Gen
import requests
import socket
import codecs 
from bs4 import BeautifulSoup
#import feedparser
import mteam_free


 
#运行设置############################################################################
#日志文件
ExecLogFile  = "log/pt.log"               #运行日志
DebugLogFile = "log/pt.debug"             #调试日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/pt.error"             #错误日志
movie.Movie.ErrorLogFile  =  ErrorLogFile
movie.Movie.ExecLogFile   =  ExecLogFile
movie.Movie.DebugLogFile  =  DebugLogFile
movie.Movie.ToBeExecDirName  =  True
movie.Movie.ToBeExecRmdir  =  False
PTPORT = 12345
#TR/QB的连接设置    
TR_IP = "localhost"
TR_PORT = 9091
TR_USER = ''
TR_PWD  = ''
QB_IPPORT = 'localhost:8989'
QB_USER = ''
QB_PWD =  ''

DBUserName = ''
DBPassword = ''
DBName     = 'db_movies'
movie.Movie.DBUserName = DBUserName
movie.Movie.DBPassword = DBPassword
movie.Movie.DBName = DBName

#连续NUMBEROFDAYS上传低于UPLOADTHRESHOLD，并且类别不属于'保种'的种子，会自动停止。
#QB：把保种的种子分类设为"保种"，就不会停止
#TR：因为不支持分类，通过制定文件夹方式来判断，如果保存路径在TRSeedFolderList中，认为属于“保种”
NUMBEROFDAYS = 1                           #连续多少天低于阈值
UPLOADTHRESHOLD = 0.02                     #阈值，上传/种子大小的比例
ToBePath = "/media/root/BT/tobe/"           #低上传的种子把文件夹移到该目录待处理
#TR的保种路径，保存路径属于这个列表的就认为是保种,，如果类别为保种的话，就不会检查是否属于lowupload
TRSeedFolderList = ["/media/root/BT/keep" ,"/root/e52/books"]
#或者手工维护一个TR分类清单，从转移保种的会自动加入。

#下载保存路径的列表，不在这个列表中的种子会报错.其中第一个路径用于创建符号链接来转移QB种子
RootFolderList = [  "/sg3t",\
                    "/media/root/SG8T",\
                    "/media/root/BT/keep",\
                    "/media/root/BT/temp",\
                    "/media/root/BT/music",\
                    "/media/root/BT/movies",\
                    "/root/e52/books" ]
TorrentListBackup = "data/pt.txt"  #种子信息备份目录（重要的是每天的上传量）

#配置自己要检查的磁盘/保存路径，看下面是否有文件夹/文件已经不在种子列表，这样就可以转移或者删除了。
CheckDiskList = [ "/media/root/SG8T","/media/root/BT/movies"]
#如果有一些文件夹/文件不想总是被检查，可以建一个忽略清单
IgnoreListFile = "data/ignore.txt"

#从QB转移到TR做种：定期检查QB状态为停止且分类为‘保种’的会转移到TR做种，转移成功后，QB种子分类会设置为'转移'
#QB的备份目录BT_backup，我的运行环境目录如下，如有不同请搜索qbittorrent在不同OS下的配置
QBBackupDir = "/root/.local/share/data/qBittorrent/BT_backup"
TRBackupDir = "/root/.config/transmission"
#转移做种以后，把种子文件和快速恢复文件转移到QBTorrentsBackupDir目录进行保存，以备需要
QBTorrentsBackupDir = "data/qb_backup"   
TRTorrentsBackupDir = "data/tr_backup"   

TrackerListBackup = "data/tracker.txt"               
TrackerDataList = [\
        {'Name':'FRDS'     ,'KeyWord':'frds'     ,'DateData':[]},\
        {'Name':'MTeam'    ,'KeyWord':'m-team'   ,'DateData':[]},\
        {'Name':'HDHome'   ,'KeyWord':'hdhome'   ,'DateData':[]},\
        {'Name':'BeiTai'   ,'KeyWord':'beitai'   ,'DateData':[]},\
        {'Name':'JoyHD'    ,'KeyWord':'joyhd'    ,'DateData':[]},\
        {'Name':'SoulVoice','KeyWord':'soulvoice','DateData':[]},\
        {'Name':'PTHome'   ,'KeyWord':'pthome'   ,'DateData':[]},\
        {'Name':'LeagueHD' ,'KeyWord':'leaguehd' ,'DateData':[]},\
        {'Name':'HDArea'   ,'KeyWord':'hdarea'   ,'DateData':[]},\
        {'Name':'PTSBao'   ,'KeyWord':'ptsbao'   ,'DateData':[]},\
        {'Name':'AVGV'     ,'KeyWord':'avgv'     ,'DateData':[]},\
        {'Name':'HDSky'    ,'KeyWord':'hdsky'    ,'DateData':[]}]
DownloadFolder = "/media/root/BT"
RSSTorrentBackupFile = "data/rss.txt"
RSSList1 = [\
    {'Name':'FRDS',  'WaitFree':False,   'Url':''},\
    {'Name':'HDSky', 'WaitFree':False,   'Url':''}]

RSSList2 = [\
    {'Name':'BeiTai',   'WaitFree':False,'Url':''},\
    {'Name':'MTeamMark','WaitFree':False,'Url':''}]
#运行设置结束#################################################################################

#程序易读性用，请勿修改
STOP    = "STOP"
GOING   = "GOING"
ERROR   = "ERROR"
TR       = "TR"
QB       = "QB"
CHECKERROR = -1
NOCHANGE   = 0
UPDATED    = 1
ADDED      = 2
LOWUPLOAD  = 3

TOBEADD    = 0 
TOBESTART  = 1
TOBEUPDATE = 2
TOBEID     = 3
DOUBAN  = 1
IMDB    = 2
MOVIE   = 0
TV      = 1
RECORD  = 2

#可变全局变量
gPTIgnoreList = []
gTorrentList = []
gRSSTorrentList = []  
global gLastCheckDate
gLastCheckDate = "1970-01-01"
global gIsNewDay
gIsNewDay = False
global gToDay
gToDay = "1970-01-01"

#记录日志用的函数############################################################
def Print(Str):
    tCurrentTime = datetime.datetime.now()
    print(tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')+"::" , end='')
    print(Str)

def LogClear(FileName) :
    if os.path.isfile(FileName):
        if os.path.isfile(FileName+".old"):    os.remove(FileName+".old")
        os.rename(FileName,FileName+".old")
      
def Log(FileName,Str) :
    fo = open(FileName,"a+")
    tCurrentTime = datetime.datetime.now()
    fo.write(tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')+"::")
    fo.write(Str+'\n')
    fo.close()

def DebugLog( Str, Mode = "np"):    
    Log(DebugLogFile,Str)
    if Mode == "p": Print(Str)

def ExecLog(Str):
    Print(Str)
    DebugLog(Str)
    Log(ExecLogFile,Str)    
    
def ErrorLog(Str):
    Print(Str)
    ExecLog(Str)
    Log(ErrorLogFile,Str)
################################################################################   


class TorrentInfo :
    def __init__(self,Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData,TotalSize,Tracker=""):
        
        self.Client = Client          #"TR" "QB"        
        self.HASH = HASH              #HASH
        #self.ID
        self.Name = Name 
        self.Done = Done              #完成率*100,取整后转换为数字
        self.Status = Status          #三种可能状态：STOP，GOING，ERROR 
                                      #for TR:Idle,Down,UP &,Seed对应GOING，Stop对应STOP
                                      #for QB:downloading，stalledUP对应GOING，PausedUP，PausedDL对应STOP
        self.Category = Category      #分类：0:保种 1:下载 2:刷上传
        self.Tags  = Tags             #标签
        self.SavedPath = SavedPath    #保存路径/media/root/BT/movies(temp),wd4t等

        self.AddDateTime = AddDateTime#种子加入时间
        self.DateData = DateData      #用于记录最近5天的上传数据，是一个数组,数组里面是字典
                                      #例如:['Date':2020-03-10,'Data':100,'Date':2020-03-11,'Data':200]
                                      #Data:，int类型，新的一天第一次数据，绝对数。单位M
                                      #正常运行时应该是每一天一条数据，而且是日期是连续的。但如果程序退出并保存数据后，很长时间再重新启动，就会出现日期不连续
                                      #这个时候会有误差，忽略不计吧
        self.Tracker = Tracker
        self.TotalSize = TotalSize
        
        self.FileName = []            #存储文件的数组
                                      #名字,大小，完成率
        self.DirName = ""             #种子目录名称
        self.RootFolder = ""          #种子保存的路径所在根目录
        self.IsRootFolder = True      #QB才有效：是否创建了子文件夹

        self.Checked = 1              #每次检查时用于标记它是否标记到，检查结束后，如果发现Checked为0，说明种子已经被删除。
                                      #新建对象时肯定Checked=1

    def CheckTorrent(self,files) :
        """
        输入：files
        返回值：
            CHECKERROR ，  出现错误
            NOCHANGE ，    没有变化
            UPDATED ，     有变化并更新完成
            ADDED ，       新增一个种子并已经加入gTorrentList列表
            LOWUPLOAD      非保种种子，最近几天上传低于阈值
        """   
        
        self.FileName = []
        for i in range(len(files)) :
            if self.Client == TR :
                Name = files[i]['name']  
                Size = files[i]['size']
                Done = (files[i]['completed']/files[i]['size'])*100
            else:
                Name = files[i].name
                Size = files[i].size
                Done = files[i].progress*100  
            self.FileName.append( {'Name':Name,'Size':Size,'Done':Done} )
        
        #首先找该种子是否存在
        tNoOfTheList = FindTorrent(self.Client,self.HASH)
        if tNoOfTheList == -1 : #没找到，说明是新种子，加入TorrentList
            gTorrentList.append(self)
            ExecLog("add torrent, name="+self.Name)
            return ADDED
        gTorrentList[tNoOfTheList].Checked = 1
        
        #获取RootFolder和DirName
        if self.GetDirName() == -1:  return CHECKERROR

        #检查文件是否存在，一天完整检查一次，否则仅检查分类不属于保种的第一个文件
        if self.Done == 100 :
            if gIsNewDay == True :
                for i in  range(len(self.FileName)):
                    if self.FileName[i]['Done'] != 100: continue
                    tFullFileName = os.path.join(self.SavedPath, self.FileName[i]['Name'])
                    if not os.path.isfile(tFullFileName):
                        ErrorLog(tFullFileName+" does not exist")
                        return CHECKERROR
                    if self.FileName[i]['Size'] != os.path.getsize(tFullFileName) :
                        ErrorLog(tFullFileName+" file size error. torrent size:"+str(self.FileName[i]['Size']))
                        return CHECKERROR
            else: #不是新的一天，对于非转移/保种/低上传分类的种子，仅检查第一个下载完成的文件是否存在
                if self.Client == TR : pass
                if self.Category == "下载" or self.Category == "刷上传" :
                    #DebugLog("check torrent file:"+self.Name+"::"+self.SavedPath)
                    for i in  range(len(self.FileName)):
                        if self.FileName[i]['Done'] != 100: continue
                        tFullFileName = os.path.join(self.SavedPath, self.FileName[0]['Name'])
                        if not os.path.isfile(tFullFileName) :
                            ErrorLog(tFullFileName+" does not exist")
                            return CHECKERROR
                        else: break

        #mteam部分免费种，免费一天，但下载完成率很低
        if self.Category == '下载' and self.Done <= 95:
            tStartTime = datetime.datetime.strptime(self.AddDateTime,"%Y-%m-%d %H:%M:%S")
            tSeconds = (datetime.datetime.now()-tStartTime).total_seconds()
            if tSeconds >= 24*3600 : ExecLog(self.Name+" have not done more than 1 day"); return CHECKERROR

        """
        #低上传且状态为停止的种子，文件转移到ToBEPath
        if self.Status == STOP and self.Category == '低上传':
            tFullPath = os.path.join(self.RootFolder,self.DirName)
            if os.path.exists(tFullPath):
                ExecLog(tFullPath+" exists, begin mv to "+ToBePath)
                try:
                    shutil.move(tFullPath, ToBePath)
                except:
                    ErrorLog("failed mv dir :"+tFullPath)
                else:
                    ExecLog("lowupload, so mv dir "+tFullPath)
        """
        
        #更新TorrentList ，进行检查和更新操作
        tUpdate = 0
        if gTorrentList[tNoOfTheList].Name        != self.Name       : gTorrentList[tNoOfTheList].Name        = self.Name       ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Done        != self.Done       : gTorrentList[tNoOfTheList].Done        = self.Done       ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Status      != self.Status     : gTorrentList[tNoOfTheList].Status      = self.Status     ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Category    != self.Category   : gTorrentList[tNoOfTheList].Category    = self.Category   ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Tags        != self.Tags       : gTorrentList[tNoOfTheList].Tags        = self.Tags       ; tUpdate += 1
        if gTorrentList[tNoOfTheList].SavedPath   != self.SavedPath  : gTorrentList[tNoOfTheList].SavedPath   = self.SavedPath  ; tUpdate += 1
        if gTorrentList[tNoOfTheList].AddDateTime != self.AddDateTime: gTorrentList[tNoOfTheList].AddDateTime = self.AddDateTime; tUpdate += 1
        if gTorrentList[tNoOfTheList].IsRootFolder != self.IsRootFolder: gTorrentList[tNoOfTheList].IsRootFolder = self.IsRootFolder; tUpdate += 1
        if gTorrentList[tNoOfTheList].RootFolder  != self.RootFolder : gTorrentList[tNoOfTheList].RootFolder  = self.RootFolder ; tUpdate += 1
        if gTorrentList[tNoOfTheList].DirName     != self.DirName    : gTorrentList[tNoOfTheList].DirName     = self.DirName    ; tUpdate += 1
        if gTorrentList[tNoOfTheList].FileName    != self.FileName   : gTorrentList[tNoOfTheList].FileName    = self.FileName   ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Tracker     != self.Tracker    : gTorrentList[tNoOfTheList].Tracker     = self.Tracker    ; tUpdate += 1        
        if gTorrentList[tNoOfTheList].TotalSize   != self.TotalSize  : gTorrentList[tNoOfTheList].TotalSize   = self.TotalSize  ; tUpdate += 1
        
        if gIsNewDay == True :   #新的一天，更新记录每天的上传量（绝对值）
            gTorrentList[tNoOfTheList].DateData.append(self.DateData[0])
            if len(gTorrentList[tNoOfTheList].DateData) >= NUMBEROFDAYS+3: del gTorrentList[tNoOfTheList].DateData[0] #删除前面旧的数据
            
            if IsLowUpload(gTorrentList[tNoOfTheList].DateData,gTorrentList[tNoOfTheList].TotalSize) :
                if self.Status != STOP and gTorrentList[tNoOfTheList].Client == QB and  gTorrentList[tNoOfTheList].Category == '下载':  return LOWUPLOAD
            return UPDATED
        elif tUpdate > 0 :   return UPDATED
        else:                return NOCHANGE      
    #end def CheckTorrent
    
    def GetDirName(self):
        """
        基于SavedPath和FileName获取一级目录DirName
        假设平常pt软件的下载保存路径为/media/root/BT/Movies，这个称之为根目录，那么这个函数的作用就是获取保存在这个路径上的一级目录名称。
        
        前提：SavedPath和FileName都必须已经获取
        
        根据，1:是否有自定义保存路径，2:是否创建子文件夹。组合出以下几种情况：
        1，有自定义保存路径，同时还创建了子文件夹，举例：
            SavedPath = /media/root/BT/Movies/1912-美-美国往事 
            FileName  = 美国往事XXX-FRDS/once.upon.XXX.mkv
                        美国往事XXX-FRDS/once.upon.XXX.nfo
            这样实际保存路径为：/media/root/BT/Movies/1912-美-美国往事/美国往事XXX-FRDS/
            DirName=1912-美-美国往事
        2、有自定义保存路径，未创建子文件夹，举例：
            SavedPath = /media/root/BT/Movies/1912-美-美国往事 
            FileName  = once.upon.XXX.mkv
                        once.upon.XXX.nfo   
            这样实际保存路径为：/media/root/BT/Movies/1912-美-美国往事/
            DirName=1912-美-美国往事
        3、未自定义保存路径，创建了子文件夹，举例：
            SavedPath = /media/root/BT/Movies 
            FileName  = 美国往事XXX-FRDS/once.upon.XXX.mkv
                        美国往事XXX-FRDS/once.upon.XXX.nfo
            这样实际保存路径为：/media/root/BT/Movies/美国往事XXX-FRDS
            DirName=美国往事XXX-FRDS
        4，未自定义保存路径，且未创建子文件夹，举例：
            SavedPath = /media/root/BT/Movies 
            FileName  = once.upon.XXX.mkv
            这种情况下，仅允许有一个文件（否则报错)用文件名当做DirName
            DirName=once.upon.XXX.mkv
        
        返回值:
            -1: 寻找DirName错误，记录日志
            0:  自定义了保存路径(情况1-2),DirName直接从SavedPath获取
            1： 未自定义保存路径(情况3-4),需要从FileName中获取
        """
    
        #先做前提条件检查,FFileName和SavedPath已经有内容
        if len(self.FileName) == 0 or self.SavedPath == "" :
            ErrorLog("no file or SavedPath is empty:"+SavedPath+"::"+str(self.FileName))
            return -1
    
        #如何判断是否创建了子文件夹IsRootFolder，所有的文件都包含了目录，而且是一致的。
        self.IsRootFolder = True; tSubDirName = ""  
        for i in range(len(self.FileName)) :
            tIndex = (self.FileName[i]['Name']).find('/')
            if tIndex == -1 :  self.IsRootFolder = False; break
            if tSubDirName == "":
                tSubDirName = (self.FileName[i]['Name'])[0:tIndex]
            else :
                if (self.FileName[i]['Name'])[0:tIndex] != tSubDirName : self.IsRootFolder = False; break
          
        #if self.Category == "转移" : Print("IsRootFolder:");Print(self.IsRootFolder)
        #if self.Category == "转移" : Print(self.FileName)

        self.SavedPath = self.SavedPath.strip()
        if self.SavedPath[-1:] == '/' : self.SavedPath = self.SavedPath[:-1] #去掉最后一个字符'/'
        
        tSplitPath = self.SavedPath.split('/')
        #Print(tSplitPath)
        i = 0 ; tIndex = 0;  tPath = "/"
        while i < len(tSplitPath) :
            tPath = os.path.join(tPath,tSplitPath[i])
            #Print(tPath)
            if tPath in RootFolderList : 
                #Print("find at:"+str(i))
                tIndex = i; break
            i += 1
        
        if tIndex == 0 : #SavedPath不在RootFolderList中
            #Print(RootFolderList)
            ErrorLog("SavedPath:"+self.SavedPath+" not in rootfolder")
            return -1
        
        if tIndex != len(tSplitPath)-1 : #情况1，2，SavedPath中包含了DirName，直接取下一层路径为DirName
            self.RootFolder = tPath
            self.DirName    = tSplitPath[tIndex+1]
            return 0
        
        #情况3-4，SavedPath就是RootFolder，需要从FileName中找DirName
        #如果只有一个文件，DirName就是这个文件
        #否则就从FileName[0]中找'/'
        self.RootFolder = self.SavedPath
        tIndex = self.FileName[0]['Name'].find('/')
        if tIndex == -1 : #情况4
            if len(self.FileName) == 1 :   self.DirName = self.FileName[0]['Name']; return  1
            else : ErrorLog("2+file in root folder:"+self.SavedPath+"::"+self.Name); return -1
        else:  #情况3
            self.DirName = self.FileName[0]['Name'][:tIndex]  #取第一个/之前的路径为DirName
        return 1    
    #end def GetDirName()      
 
#end class TorrentInfo        

def SaveTorrent(torrent):
    """
    0、暂停种子
    1、从rss表中获取toubanid和imdbid
    2、根据doubanid或者imdbid刮削豆瓣电影信息
    3、移入或者更名至tobe目录下的目录文件夹
    4 下载poster.jpg文件    
    5、检查该目录并加入表
    6、更新豆瓣刮削信息到表movies
    7、把种子分类设为空  
    """
    
    global g_DB
    global g_MyCursor
    try: torrent.pause()
    except: ErrorLog("failed to stop torrent:"+torrent.name); return False
    
    #1、从rss表中获取doubanid和imdbid,Name,Nation,Director等信息
    HASH = torrent.hash
    g_DB = mysql.connector.connect( host="localhost",  user=DBUserName,  passwd=DBPassword, database=DBName)
    g_MyCursor = g_DB.cursor()
    sel_sql = 'select DoubanID,IMDBID,Type,Name,Nation,Director,Actors,downloadlink from rss where id = %s'
    sel_val = (HASH,)
    g_MyCursor.execute(sel_sql,sel_val)
    SelectResult = g_MyCursor.fetchall()
    if len(SelectResult) != 1: ErrorLog("failed to select from rss :{}".format(torrent.name)); return False
    tDoubanID = SelectResult[0][0]
    tIMDBID   = SelectResult[0][1]
    tType     = SelectResult[0][2]
    tName     = SelectResult[0][3]
    tNation   = SelectResult[0][4]
    tDirector = SelectResult[0][5]
    tActors   = SelectResult[0][6]
    tDownloadLink = SelectResult[0][7]
    ExecLog("{}:{}::{}::{}::{}::{}::{}::{}".format(HASH,tDoubanID,tIMDBID,tType,tName,tNation,tDirector,tActors))
    
    tEpisodes=0
    tForeignName=tPoster=tDoubanScore=tIMDBScore=tOtherNames=tGenre=""
    #2、根据doubanid或者imdbid刮削豆瓣电影信息
    tMovieInfo = {"success":False}
    if tDoubanID != "" :   tMovieInfo = Gen({'site':'douban','sid':tDoubanID}).gen(_debug=True)
    elif tIMDBID != "" :   tMovieInfo = Gen({'site':'douban','sid':tIMDBID  }).gen(_debug=True)
    else :  ErrorLog("empty link:"+torrent.name)
    if tMovieInfo["success"]: 
        if tMovieInfo['episodes'] == "": tMovieInfo['episodes'] = '0'
        if tMovieInfo['year']     == "": tMovieInfo['year']     = '0'   
        tNation      = (tMovieInfo['region'][0]).strip()
        tYear        = int(tMovieInfo['year'])
        tDoubanID    = tMovieInfo['sid']
        tIMDBID      = tMovieInfo['imdb_id']
        tName        = tMovieInfo['chinese_title']
        tForeignName = tMovieInfo['foreign_title']
        tDirector    = ','.join(tMovieInfo['director'])
        tActors      = ','.join(tMovieInfo['cast'])
        tEpisodes    = int(tMovieInfo['episodes'])
        tPoster      = tMovieInfo['poster']
        tDoubanScore = tMovieInfo['douban_rating_average']
        tIMDBScore   = tMovieInfo['imdb_rating']
        tOtherNames  = ','.join(tMovieInfo['aka'])
        tGenre       = ','.join(tMovieInfo['genre'])
            
        if   tNation[-1:] == '国' : tNation = tNation[:-1]  #去除国家最后的国字
        elif tNation == '香港'    : tNation = '港'
        elif tNation == '中国香港': tNation = '港'
        elif tNation == '中国大陆': tNation = '国'
        elif tNation == '中国台湾': tNation = '台'
        elif tNation == '日本'    : tNation = '日'
        else : pass
        tIndex = tIMDBScore.find('/')
        if tIndex > 0: tIMDBScore = tIMDBScore[:tIndex]
        else:          tIMDBScore = ""
        #判断类型，纪录片，电视剧，电影
        if tGenre.find('纪录') >= 0 :tType = RECORD
        elif tEpisodes > 0          :tType = TV
        else                        :tType = MOVIE            
    else: ErrorLog("failed to request from douban:"+torrent.name)
    
    if tName == "" or tNation == "" or tIMDBID == "" : ExecLog("empty name or nation or imdbid"); return False
    
    #3、移入或者更名至tobe目录下的目录文件夹 
    #3.1 组装目标文件夹名需要先获取Number和Copy
    Number = Copy = 0
    if tIMDBID == "" : ErrorLog("empty IMDBID:"+torrent.name); return False
    g_DB = mysql.connector.connect( host="localhost",  user=DBUserName,  passwd=DBPassword , database=DBName)
    g_MyCursor = g_DB.cursor()
    sel_sql = 'select number,copy from movies where imdbid = %s'
    sel_val = (tIMDBID,)
    g_MyCursor.execute(sel_sql,sel_val)
    SelectResult = g_MyCursor.fetchall()
    if len(SelectResult) == 0: #说明不存在，需要获取max(number)+1
        sel_sql = 'select max(number) from movies'
        g_MyCursor.execute(sel_sql)
        SelectResult = g_MyCursor.fetchall()
        Number = SelectResult[0][0]+1
    elif len(SelectResult) == 1:
        Number = SelectResult[0][0]
        Copy   = SelectResult[0][1]
    else:
        #多条记录，有可能是正常的，也可能是异常的。先取第一条记录的Number,记录下日志，待手工检查
        ExecLog("2+ record in movies where imdbid = "+IMDBID)
        Number = SelectResult[0][0]
        for i in range(len(SelectResult)):
            if SelectResult[i][0] != Number: ErrorLog("diff number in case of same imdbid:"+IMDBID); break
    g_DB.close()
    
    #3.2 组装新的目标文件夹名
    tTorrentName = re.sub(u"[\u4e00-\u9f50]+","",torrent.name) #去掉name中的中文字符
    tTorrentName = tTorrentName.strip()                         #去掉前后空格
    if tTorrentName[:1] == '.': tTorrentName = tTorrentName[1:] #去掉第一个.
    #部分种子只有一个视频文件，name会以.mkv类似格式结尾
    if tTorrentName[-4:] == '.mp4' or tTorrentName[-4:] == '.mkv' or tTorrentName[-4:] == 'avi' or tTorrentName[-4:] == 'wmv': tTorrentName = tTorrentName[:-4]
    if Copy > 0 : DirName = str(Number).zfill(4)+'-'+str(Copy)+'-'+tNation
    else        : DirName = str(Number).zfill(4)              +'-'+tNation
    if   tType == 0: DirName +=              '-'+tName+' '+tTorrentName
    elif tType == 1: DirName += '-'+'电视剧'+'-'+tName+' '+tTorrentName
    elif tType == 2: DirName += '-'+'纪录片'+'-'+tName+' '+tTorrentName
    else: ErrorLog("error type:"+tType)

    #3.3 移动或者更名至目标文件夹
    tSaveDirName = os.path.join(torrent.save_path,torrent.name)
    tToBeDirName = os.path.join(ToBePath,torrent.name)
    DestDirName  = os.path.join(ToBePath,DirName)
    if os.path.exists(DestDirName):   ExecLog("DirName exists:"+DestDirName)
    else:
        if os.path.exists(tToBeDirName):  srcDirName = tToBeDirName  #从tobe目录中去改名
        else:                             srcDirName = tSaveDirName  #去原始保存目录移动到目标目录
        try:
            #原种子没有目录只是一个文件，那就新建目标目录，move函数就会把这个文件移动到目标目录
            if os.path.isfile(srcDirName): os.mkdir(DestDirName) 
            shutil.move(srcDirName,DestDirName)
        except Exception as err:
            ErrorLog("failed to mv dir:"+DestDirName)
            Print(err)
            return False
        else:  ExecLog("success mv dir to tobe:"+DestDirName)

    #4 下载poster.jpg文件
    DestFullFile=os.path.join(DestDirName,"poster.jpg")
    try:
        f=requests.get(tPoster)
        with open(DestFullFile,"wb") as code:
            code.write(f.content)
    except Exception as err:
        Print(err)
        ErrorLog("failed to download poster.jpg from:"+tPoster)
    else : ExecLog("success download jpg file")

    #5 检查该目录并加入表
    tMovie = movie.Movie(ToBePath, DirName)
    if tMovie.CheckMovie() != 1      :  ErrorLog("failed to check:"+DirName)  #; continue，继续插入表
    if tMovie.CheckTable("tobe") != 1:  ErrorLog("faied to table:"+DirName); return False
    else : ExecLog("success insert table")
    
    #6 更新豆瓣刮削信息到表movies
    g_DB = mysql.connector.connect(host="localhost", user=DBUserName, passwd=DBPassword, database=DBName)
    g_MyCursor = g_DB.cursor()
    up_sql = "update movies set \
             DoubanID=%s,IMDBID=%s,ForeignName=%s,Director=%s,Actors=%s,Episodes=%s,Poster=%s,DoubanScore=%s,IMDBScore=%s,OtherNames=%s,DownloadLink=%s,HASH=%s,Genre=%s where Number=%s and Copy=%s"
    up_val =(tDoubanID,  tIMDBID,  tForeignName,  tDirector,  tActors,  tEpisodes, tPoster,  tDoubanScore,   tIMDBScore, tOtherNames,  tDownloadLink, HASH,tGenre,         Number,       Copy)
    try:
        g_MyCursor.execute(up_sql,up_val)
        g_DB.commit()
    except Exception as err:
        Print(err)
        ErrorLog("update error:"+DirName+":"+up_sql)
        g_DB.close()
        return False
    else:
        g_DB.close()
        ExecLog("success update table:"+DirName)
    
    #7 把种子分类设为空    
    torrent.set_category(category="")
    return True
    
def TransformTorrent(Client,torrent):
    """
    将torrent转化为一个TorrentInfo实例并返回
    """
    if Client == TR:
        HASH = torrent.hashString
        Name = torrent.name
        Done = int(torrent.percentDone*100)
        #Status = torrent.status 
        if torrent.status[0:4].lower() == "stop": Status = STOP
        else                                    : Status = GOING
        Category = ""
        Tags = ""
        SavedPath = torrent.downloadDir
        AddDateTime = time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime(torrent.addedDate) ) 
        Tracker = torrent.trackers[0]['announce']
        DateData = [] ; DateData.append({'Date':gToDay,'Data':torrent.uploadedEver})  
        TotalSize = torrent.totalSize
    else :
        HASH = torrent.hash
        Name = torrent.name
        Done = int(torrent.progress*100)
        if torrent.state[:5].lower() == "pause" : Status = STOP
        else :                                    Status = GOING
        Category = torrent.category
        Tags = torrent.tags
        SavedPath = torrent.save_path
        AddDateTime = time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime(torrent.added_on) ) 
        Tracker = torrent.tracker
        DateData = [] ; DateData.append({'Date':gToDay,'Data':torrent.uploaded})  
        TotalSize = torrent.total_size

    return  TorrentInfo(Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData,TotalSize,Tracker)
    
def IsLowUpload(DateData,TotalSize):
    """
    检查DateData中的数据，如果连续三天上传增量数据低于阈值就返回1，否则返回0
    """
    #包括今天在内，至少要有NUMBEROFDAYS+1天数据
    tLength = len(DateData)
    if tLength < NUMBEROFDAYS + 1:     return False

    #从尾部开始循环，尾部日期是最新的
    i = tLength - 1; tDays = 0  
    while i > 1 and tDays < NUMBEROFDAYS:
        tDeltaData = (DateData[i])['Data'] - (DateData[i-1])['Data']
        if tDeltaData/TotalSize < UPLOADTHRESHOLD :    tDays += 1
        else:    return False  #有一天高于阈值就退出
        i -= 1
    
    #运行到这，tDays应该就等于NUMBEROFDAYS,不过代码还是加一个判断
    if tDays >= NUMBEROFDAYS : return True
    else : return False
        
def FindTorrent(Client,HASH):
    """
    根据HASH寻找TorrentList，如果找到就返回序号，否则返回-1
    """
    for i in range(len(gTorrentList)) :
        if HASH == gTorrentList[i].HASH and gTorrentList[i].Client == Client :  return i

    return -1   
    
def ReadPTBackup():
    """
    读取备份目录下的pt.txt，用于恢复种子记录数据，仅当初始化启动时调用
    """
    
    global gTorrentList
    global gLastCheckDate
    
    if not os.path.isfile(TorrentListBackup): ExecLog(TorrentListBackup+" does not exist"); return 0
        
    for line in open(TorrentListBackup):
        Client,HASH,Name,tDoneStr,Status,Category,Tags,SavedPath,AddDateTime,RootFolder,DirName,tDateDataStr = line.split('|',11)
        Done = int(float(tDoneStr))
        if tDateDataStr [-1:] == '\n' :  tDateDataStr = tDateDataStr[:-1]  #remove '\n'
        tDateDataList = tDateDataStr.split(',')
        DateData = []
        for i in range(len(tDateDataList)) :
            if tDateDataList[i] == "" :  break      #最后一个可能为空就退出循环
            tDate = (tDateDataList[i])[:10]
            tData = int( (tDateDataList[i])[11:] )
            DateData.append({'Date':tDate,'Data':tData})

        gTorrentList.append(TorrentInfo(Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData,0))
        gTorrentList[-1].RootFolder = RootFolder
        gTorrentList[-1].DirName = DirName
    #end for 
    
    gLastCheckDate = tDate
    return 1

def WritePTBackup():
    """
    把当前种子列表写入备份文件
    1、每一天把昨天的文件备份成TorrentListBackup+"."+gLastCheckDate，例如pt.txt.2020-03-17
    2、删除不是这个月以及上个月日期的所有备份文件（最多保留当前月及上月的备份数据）
    3、当天的备份文件为TorrentListBackup+".old" 
    """

    if gIsNewDay == True :
        DebugLog("new day is :"+gToDay)
        tThisMonth = gToDay[0:7] ; tThisYear = gToDay[0:4]
        if tThisMonth[5:7] == "01" :  tLastMonth = str(int(tThisYear)-1)+"-"+"12"      
        else                       :  tLastMonth = tThisYear+"-"+str(int(tThisMonth[5:7])-1).zfill(2)
        
        tFileName = os.path.basename(TorrentListBackup)
        tLength = len(tFileName)
        tDirName = os.path.dirname(TorrentListBackup)
        for file in os.listdir(tDirName):
            if file[:tLength] == tFileName and len(file) == tLength+11:  #说明是TorrentListBackup的每天备份文件
                if file[tLength+1:tLength+8] != tLastMonth and file[tLength+1:tLength+8] != tThisMonth : #仅保留这个月和上月的备份文件
                    try :   os.remove(os.path.join(tDirName,file))
                    except: ErrorLog("failed to delete file:"+os.path.join(tDirName,file))
        
        #把旧文件备份成昨天日期的文件,后缀+"."+gLastCheckDate
        tLastDayFileName = TorrentListBackup+"."+gLastCheckDate
        if os.path.isfile(TorrentListBackup) :
            if  os.path.isfile(tLastDayFileName) : os.remove(tLastDayFileName)
            os.rename(TorrentListBackup,tLastDayFileName) 
            DebugLog("backup pt file:"+tLastDayFileName)
    else : LogClear(TorrentListBackup)        

    try : fo = open(TorrentListBackup,"w")
    except: ErrorLog("Error:open ptbackup file to write："+TorrentListBackup); return -1
        
    for i in range(len(gTorrentList)):
        tDateDataListStr = ""
        for j in range( len(gTorrentList[i].DateData) ):        
            tDateDataStr = gTorrentList[i].DateData[j]['Date']+":" + str(gTorrentList[i].DateData[j]['Data'])
            tDateDataListStr += tDateDataStr+','
        if tDateDataListStr[-1:] == ',' : tDateDataListStr = tDateDataListStr[:-1] #去掉最后一个','
        tStr  =     gTorrentList[i].Client+'|'
        tStr +=     gTorrentList[i].HASH+'|'
        tStr +=     gTorrentList[i].Name+'|'
        tStr += str(gTorrentList[i].Done)+'|'
        tStr +=     gTorrentList[i].Status+'|'
        tStr +=     gTorrentList[i].Category+'|'
        tStr +=     gTorrentList[i].Tags+'|'
        tStr +=     gTorrentList[i].SavedPath+'|'
        tStr +=     gTorrentList[i].AddDateTime+'|'
        tStr +=     gTorrentList[i].RootFolder+'|'
        tStr +=     gTorrentList[i].DirName+'|'
        tStr +=     tDateDataListStr+'\n'
        fo.write(tStr)
  
    fo.close()
    return 1
#end def WritePTBackup
    
def CheckTorrents(Client):
    """
    进行TR/QB的所有种子进行检查和分析，并更新列表
    1、检查DIRName是否存在，否则暂停种子
    2、NEWDAY下：比对所有文件，大小，错误，暂停种子
    3、QB下，检查标签设置
    4、更新种子信息列表（增加，删除，更新）
    5、NEWDAY：计算DATA，低于阈值的暂停种子
    
    返回值：-1:错误，0:无更新，1:有更新 ，用于指示是否需要备份文件
    """
    global gTorrentList
    
    tNumberOfAdded = 0
    tNumberOfDeleted = 0
    tNumberOfUpdated = 0
    tNumberOfPaused = 0 
    tNumberOfError = 0
    tNumberOfNoChange = 0
    tNumberOfTorrent = 0

    #先把检查标志复位
    for i in range( len(gTorrentList) ):
        if gTorrentList[i].Client == Client : gTorrentList[i].Checked = 0

   
    #连接Client并获取TorrentList列表
    try:
        if Client == TR :
            tr_client = transmissionrpc.Client(TR_IP, port=TR_PORT,user=TR_USER,password=TR_PWD)
            torrents = tr_client.get_torrents()
        else :
            qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
            qb_client.auth_log_in()
            torrents = qb_client.torrents_info()            
        DebugLog("connect to  "+Client)
    except:
        ErrorLog("failed to connect to "+Client)
        return -1
        
    # 开始逐个获取torrent并检查
    for torrent in torrents: 
        tTorrentInfo = TransformTorrent(Client,torrent)
        
        if Client == TR:  tReturn = tTorrentInfo.CheckTorrent(torrent.files())
        else :            tReturn = tTorrentInfo.CheckTorrent(torrent.files)
          
        if tReturn == CHECKERROR :        tNumberOfError += 1
        elif tReturn == LOWUPLOAD :       tNumberOfPaused += 1
        elif tReturn == ADDED :           tNumberOfAdded += 1
        elif tReturn == UPDATED :         tNumberOfUpdated += 1
        elif tReturn == NOCHANGE:         tNumberOfNoChange += 1
        else: ErrorLog("unknown return in CheckTorrent:"+str(tReturn))

        if tReturn == CHECKERROR :  
            if Client == TR:  torrent.stop()
            else :            torrent.pause()
            ExecLog("stop torrent for error, name="+torrent.name)
        if tReturn == LOWUPLOAD : 
            #if Client == TR:   torrent.stop()
            #else :             torrent.pause();  torrent.set_category('低上传')
            #ExecLog("stop torrent for low upload, name="+torrent.name)
            if Client == QB : torrent.set_category('低上传')
            ExecLog("low upload torrent:"+torrent.name)

        #对于QB
        #检查并设置标签
        #对于category为save的种子进行转移和保存操作
        #对于category为转移的种子进行转移TR进行做种
        if Client == QB:
            Tracker = torrent.tracker
            Tags = torrent.tags
            if Tracker.find("keepfrds") >= 0 :
                if Tags != 'frds':
                    torrent.remove_tags()
                    torrent.add_tags('frds')
            elif Tracker.find("m-team") >= 0 :
                if Tags != 'mteam':
                    torrent.remove_tags()
                    torrent.add_tags('mteam')
            elif Tracker.find("hdsky") >= 0 :
                if Tags != 'hdsky':
                    torrent.remove_tags()
                    torrent.add_tags('hdsky')
            elif Tracker == "" : pass
            else:
                if Tags != 'other':
                    torrent.remove_tags()
                    torrent.add_tags('other')
            
            if torrent.category == "save" : SaveTorrent(torrent)
            if torrent.category == "转移" : MoveTorrent(torrent)
        #endif Client == QB
        
        tNumberOfTorrent += 1
    #end for tr torrent 
    
    #最后，找出没有Checked标志的种子列表，进行删除操作。
    i = 0; tLength = len(gTorrentList)
    while i < len(gTorrentList) :
        if gTorrentList[i].Checked == 0 and gTorrentList[i].Client == Client:
            tNumberOfDeleted += 1
            ExecLog("del torrent, name="+gTorrentList[i].Name)
            del gTorrentList[i] 
        else:
            i += 1                
 
    DebugLog("complete CheckTorrents  from "+Client)
    if tNumberOfAdded > 0   : DebugLog(str(tNumberOfAdded).zfill(4)+" torrents added")
    if tNumberOfDeleted > 0 : DebugLog(str(tNumberOfDeleted).zfill(4)+" torrents deleted")
    if tNumberOfUpdated > 0 : DebugLog(str(tNumberOfUpdated).zfill(4)+" torrents updated")
    if tNumberOfError > 0   : DebugLog(str(tNumberOfError).zfill(4)+" torrents paused for error")
    if tNumberOfPaused > 0 : DebugLog(str(tNumberOfPaused).zfill(4)+" torrents paused for low upload")
    if  tNumberOfAdded >= 1 or \
        tNumberOfDeleted >= 1 or \
        tNumberOfUpdated >= 1 or \
        tNumberOfError >= 1 or \
        tNumberOfPaused >= 1 :
        if WritePTBackup() == 1:   ExecLog(str(len(gTorrentList)).zfill(4)+" torrents writed.")  
        return 1
    else :
        return 0
#end def CheckTorrents()    

def ReadIgnoreList() :
    """
    从IgnoreListFile读取忽略的文件夹/名，加入gPTIgnoreList
    返回值：1文件存在，0文件不存在
    """
    
    if os.path.isfile(IgnoreListFile):
        #Print("find file:"+IgnoreListFile)
        for line in open(IgnoreListFile):
            Path,Name = line.split('|',1)
            Path = Path.strip(); Name = Name.strip()
            if Name[-1:] == '\n' : Name = Name[:-1]
            gPTIgnoreList.append({'Path':Path,'Name':Name})
            #Print(gPTIgnoreList[-1]['Path']+"::"+gPTIgnoreList[-1]['Name'])
        return 1
    else :
        Print("not find file:"+IgnoreListFile)
        ExecLog(IgnoreListFile+" is not exist")
        return 0

def InPTIgnoreList(SavedPath,DirName) :

    if SavedPath[-1:] == '/' : SavedPath = SavedPath[:-1]
    for i in range( len(gPTIgnoreList) ) :
        if (gPTIgnoreList[i])['Path'] == SavedPath and (gPTIgnoreList[i])['Name'] == DirName:  return True

    return False

def InTorrentList(SavedPath,DirName):
    """
    判断SavedPath+DirName在不在TorrentList
    """
    for i in range( len(gTorrentList) ) :
        tSrcDirName = os.path.join(SavedPath,DirName)
        tDestDirName = os.path.join(gTorrentList[i].RootFolder,gTorrentList[i].DirName)
        if os.path.realpath(tSrcDirName) == os.path.realpath(tDestDirName): 
            DebugLog(os.path.realpath(tSrcDirName))
            DebugLog(os.path.realpath(tDestDirName))
            DebugLog(gTorrentList[i].Name+"::"+gTorrentList[i].HASH)
            return True
    return False
#end def InTorrentList
    
def CheckDisk(tCheckDiskList):
    """
    对Path下的目录及文件逐个对比TorrentList，并进行标记。
    """

    tDirNameList = []
    for DiskPath in tCheckDiskList:
        DebugLog("begin check:"+DiskPath)
        for file in os.listdir(DiskPath):        
            fullpathfile = os.path.join(DiskPath,file)
            if os.path.isdir(fullpathfile) or os.path.isfile(fullpathfile) :        
                #一些特殊文件夹忽略
                if file == 'lost+found' or file[0:6] == '.Trash' :
                    DebugLog ("ignore some dir:"+file)
                    continue 
            
                if InPTIgnoreList(DiskPath,file):
                    DebugLog ("in Ignore List:"+DiskPath+"::"+file)
                    continue
                
                #合集
                if os.path.isdir(fullpathfile) and len(file) >= 9 and re.match("[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]",file[:9]) :
                    for file2 in os.listdir(fullpathfile):
                        fullpathfile2 = os.path.join(fullpathfile,file2)
                        if os.path.isfile( fullpathfile2) : continue
                        if InPTIgnoreList(fullpathfile,file2):
                            DebugLog("in Ignore List:"+fullpathfile2)
                            continue
                        if InTorrentList(fullpathfile,file2): DebugLog(file2+":: find in torrent list")
                        else: ExecLog(file2+":: not find in torrent list"); tDirNameList.append({'DirPath':fullpathfile,'DirName':pathfile2})
                else:
                    if InTorrentList(DiskPath,file) : DebugLog(file+"::find in torrent list:")
                    else :                            ExecLog(file+"::not find in torrent list:"); tDirNameList.append({'DirPath':DiskPath,'DirName':file})
            else :
                ExecLog("Error：not file or dir")
    return tDirNameList
#end def CheckDisk

def MoveTorrent(qb_torrent):
    """
    转移到tr去保种
    返回值：
    
    1、备份转移种子的torrent文件和fastresume文件
    2、在BT/keep创建链接到savedpath
    2、调用tr增加种子
    4，修改QB标签为""
    """

    #Print("begin move")

    qb_torrent.pause()
    
    #备份转移种子的torrent文件和fastresume文件
    tTorrentFile = os.path.join(QBBackupDir,qb_torrent.hash+".torrent")
    tDestTorrentFile = os.path.join(QBTorrentsBackupDir,qb_torrent.hash+".torrent")
    tResumeFile  = os.path.join(QBBackupDir,qb_torrent.hash+".fastresume")
    tDestResumeFile  = os.path.join(QBTorrentsBackupDir,qb_torrent.hash+".fastresume")
    try:
        shutil.copyfile(tTorrentFile,tDestTorrentFile)
        shutil.copyfile(tResumeFile ,tDestResumeFile)
    except:
        #Print(tTorrentFile)
        #Print(tResumeFile)
        #Print(tDestTorrentFile)
        ErrorLog("failed to copy torrent and resume file:"+gTorrentList[i].HASH)
        return False
    else: ExecLog("success backup torrent file to :"+QBBackupDir)


    #Print(str(gTorrentList[i].IsRootFolder)+'|'+gTorrentList[i].SavedPath+'|'+gTorrentList[i].RootFolder+'|'+gTorrentList[i].DirName)
    #for file in gTorrentList[i].FileName: Print(file)
    tNoOfList = FindTorrent(QB,qb_torrent.hash)
    if tNoOfList < 0 : ErrorLog("not find in torent list:"+qb_torrent.hash); return False

    Print(gTorrentList[tNoOfList].IsRootFolder)
    Print(gTorrentList[tNoOfList].RootFolder)
    Print(gTorrentList[tNoOfList].SavedPath)
    if gTorrentList[tNoOfList].IsRootFolder == True :   tDestSavedPath = os.path.realpath(gTorrentList[tNoOfList].SavedPath)
    else :   #为TR的保存路径创建链接
        if gTorrentList[tNoOfList].Name[-4:] == '.mkv' : gTorrentList[tNoOfList].Name = gTorrentList[tNoOfList].Name[:-4] #移除.mkv
        tLink = os.path.join(TRSeedFolderList[0],gTorrentList[tNoOfList].Name) 
        try:    
            if not os.path.exists(tLink) : os.symlink(os.path.realpath(gTorrentList[tNoOfList].SavedPath),tLink)
        except:
            ErrorLog("failed create link:ln -s "+os.path.realpath(gTorrentList[tNoOfList].SavedPath)+" "+tLink)
            return False            
        tDestSavedPath = TRSeedFolderList[0]
    #TR加入种子
    try:
        tr_client = transmissionrpc.Client(TR_IP, port=TR_PORT,user=TR_USER,password=TR_PWD)
        tr_torrent = tr_client.add_torrent(torrent=tTorrentFile,download_dir=tDestSavedPath,paused=True)
    except ValueError as err:
        Print(err)
        ErrorLog("failed to add torrent:"+tTorrentFile)
        return False
    except  transmissionrpc.TransmissionError as err:
        Print(err)
        ErrorLog("failed to add torrent:"+tTorrentFile)
        return False            
    except transmissionrpc.HTTPHandlerError as err:
        Print(err)
        ErrorLog("failed to add torrent:"+tTorrentFile)
        return False               
    else:
        ExecLog("move torrent to tr:"+tr_torrent.name+'::'+tr_torrent.hashString)
    #QB设置类别为""
    try: qb_torrent.set_category("")
    except: ErrorLog("failed to set category:"+gTorrentList[tNoOfList].Name)
    else: gTorrentList[tNoOfList].Category = ""

    return True
#end def MoveTorrents    
    
def RestartQB():

    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        qb_client.torrents.pause.all()
        qb_client.app_shutdown()
    except:
        ExecLog("failed to stop QB")
        return False
    else:
        ExecLog("success to stop QB")
        
    time.sleep(600)
    if os.system("/usr/bin/qbittorrent &") == 0 : ExecLog ("success to start qb")
    else : ExecLog("failed to start qb"); return False
    
    time.sleep(10)
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)
        qb_client.auth_log_in()
        torrents = qb_client.torrents.info()
    except:
        debugLog("failed to resume qb torrents")
        return False
        
    for torrent in torrents:
        if torrent.category == '下载' or torrent.category == '刷上传' or torrent.category == '保种' or torrent.category == 'sky-save': 
            try: torrent.resume()
            except: ExecLog("failed to resume:"+torrent.name)
    return True
    
def TrackerData():
    """
    统计各站点的上传量
    """
    
    for i in range(len(TrackerDataList)):
        TrackerDataList[i]['DateData'].append( {'Date':gToDay,'Data':0} )
        if len(TrackerDataList[i]['DateData']) >= 30: del TrackerDataList[i]['DateData'][0]

    for i in range(len(gTorrentList)):
        if   len(gTorrentList[i].DateData) == 0 :ErrorLog("datedata is null:"+gTorrentList[i].HASH);  continue
        elif len(gTorrentList[i].DateData) == 1 :tData = gTorrentList[i].DateData[0]['Data']
        else                                    :tData = gTorrentList[i].DateData[-1]['Data']-gTorrentList[i].DateData[-2]['Data']
    
        Tracker = gTorrentList[i].Tracker
        IsFind = False
        for j in range(len(TrackerDataList)):
            if Tracker.find(TrackerDataList[j]['KeyWord']) >= 0 : 
                TrackerDataList[j]['DateData'][-1]['Data'] += tData
                IsFind = True ; break
        if IsFind == False: ErrorLog("unkown tracker:"+Tracker)

    TotalUpload = 0
    for i in range(len(TrackerDataList)):
        tUpload = TrackerDataList[i]['DateData'][-1]['Data']; TotalUpload += tUpload
        ExecLog( "{} upload(G):{}".format((TrackerDataList[i]['Name']).ljust(10),round(tUpload/(1024*1024*1024),3)) )
    ExecLog( "{} upload(G):{}".format("total".ljust(10), round(TotalUpload/(1024*1024*1024),3)) )
    ExecLog( "average upload radio :{}M/s".format( round(TotalUpload/(1024*1024*24*3600),2) ) )
        
    for i in range(len(TrackerDataList)):
        tDateData = TrackerDataList[i]['DateData']
        j=len(tDateData)-1
        NumberOfDays=0
        while j >= 0 :
            if tDateData[j]['Data'] == 0 :NumberOfDays += 1
            else                         :break
            j -= 1
        ExecLog( "{} {} days no upload".format(TrackerDataList[i]['Name'].ljust(10),str(NumberOfDays).zfill(2)) )
    
    WriteTrackerBackup()
    return 1
    
def ReadTrackerBackup():
    """
    读取TrackerList的备份文件，用于各个Tracker的上传数据
    """
    global TrackerDataList 
    
    if not os.path.isfile(TrackerListBackup):
        ExecLog(TrackerListBackup+" does not exist")
        return 0
        
    for line in open(TrackerListBackup):
        Tracker,tDateDataStr = line.split('|',1)
        if tDateDataStr [-1:] == '\n' :  tDateDataStr = tDateDataStr[:-1]  #remove '\n'
        tDateDataList = tDateDataStr.split(',')
        DateData = []
        for i in range( len(tDateDataList) ):
            if tDateDataList[i] == "" :  break      #最后一个可能为空就退出循环
            tDate = (tDateDataList[i])[:10]
            tData = int( (tDateDataList[i])[11:] )
            DateData.append({'Date':tDate,'Data':tData})

        IsFind = False
        for i in range(len(TrackerDataList)):
            if Tracker == TrackerDataList[i]['Name'] : 
                TrackerDataList[i]['DateData'] = DateData
                IsFind = True
        if IsFind == False: ErrorLog("unknown tracker in TrackerBackup:"+Tracker)
                
    #end for 
    return 1
        
def WriteTrackerBackup():

    if gIsNewDay == True :
        tThisMonth = gToDay[0:7] ; tThisYear = gToDay[0:4]
        if tThisMonth[5:7] == "01" : tLastMonth = str(int(tThisYear)-1)+"-"+"12"      
        else                       : tLastMonth = tThisYear+"-"+str(int(tThisMonth[5:7])-1).zfill(2)
        
        tFileName = os.path.basename(TrackerListBackup)
        tLength = len(tFileName)
        tDirName = os.path.dirname(TrackerListBackup)
        for file in os.listdir(tDirName):
            if file[:tLength] == tFileName and len(file) == tLength+11:  #说明是TorrentListBackup的每天备份文件
                if file[tLength+1:tLength+8] != tLastMonth and file[tLength+1:tLength+8] != tThisMonth : #仅保留这个月和上月的备份文件
                    try :   os.remove(os.path.join(tDirName,file))
                    except: ErrorLog("failed to delete file:"+os.path.join(tDirName,file))
        
        #把旧文件备份成昨天日期的文件,后缀+"."+gLastCheckDate
        tLastDayFileName = TrackerListBackup+"."+gLastCheckDate
        if os.path.isfile(TrackerListBackup) :
            if  os.path.isfile(tLastDayFileName) : os.remove(tLastDayFileName)
            os.rename(TrackerListBackup,tLastDayFileName) 
    else :LogClear(TrackerListBackup)        

    try   :  fo = open(TrackerListBackup,"w")
    except:  ErrorLog("Error:open ptbackup file to write："+TrackerListBackup); return -1

    for i in range(len(TrackerDataList)):
        tDateDataList = TrackerDataList[i]['DateData']
        tDateDataListStr = ""
        for j in range(len(tDateDataList)):        
            tDateDataStr = tDateDataList[j]['Date']+":" + str(tDateDataList[j]['Data'])
            tDateDataListStr += tDateDataStr+','
        if tDateDataListStr[-1:] == ',' : tDateDataListStr = tDateDataListStr[:-1] #去掉最后一个','
        tStr = TrackerDataList[i]['Name'] + '|' + tDateDataListStr + '\n'
        fo.write(tStr)
             
    fo.close()
    ExecLog("success write tracklist")
    
    return 1
#end def WritePTBackup

class RSSTorrent:
    def __init__ (self,RSSName,HASH,Title,DownloadLink,Status,DoubanID="",IMDBID=""):
        self.RSSName = RSSName
        self.HASH  = HASH
        self.Title = Title
        self.DownloadLink = DownloadLink
        self.Status = Status     #TOBEADD,TOBESTART,TOBEUPDATE
        self.DoubanID = DoubanID
        self.IMDBID = IMDBID
        self.ToBeDeleted = False
        self.ErrorTimes = 0

def GetTorrentID(DownloadLink):
    TorrentID = ""

    Index = DownloadLink.find("id=")
    if Index == -1: ExecLog("failed to find torrentid starttag(id=):"+DownloadLink) ;return ""
    TorrentID = DownloadLink[Index+3:]
    Index = TorrentID.find("&")
    if Index == -1: ExecLog("failed to find torrentid endtag(&):"+DownloadLink); return ""
    TorrentID = TorrentID[:Index]
    return TorrentID
        
def GetIDFromLink(tempstr,tag):
    if tempstr == "": return ""
    if tag == DOUBAN: tIndex = tempstr.find("douban.com")
    else: tIndex = tempstr.find("imdb.com")
    if tIndex == -1 : return ""
    tempstr = tempstr.strip(' ')
    if tempstr[-1:] == '/': tempstr = tempstr[:-1]
    tIndex = tempstr.rfind('/')
    if tIndex == -1: return ""
    return tempstr[tIndex+1:]
    
def GetIDFromNfo(torrent,tIndex):     

    #检查下有没有nfo文件
    tNfoFileName = ""
    for file in torrent.files:
        if file.name[-4:].lower() == '.nfo' :
            tNfoFileName = os.path.join(torrent.save_path,file.name)
            ExecLog("success find nfo file:"+torrent.name)
            break
    if tNfoFileName == "": ExecLog("can't find nfo file:"+torrent.name); return -1
    
    IMDBLink = DoubanLink = ""
    for line in open(tNfoFileName,"rb"):
        line = line.decode("utf8","ignore")
        if line[-1:] == '\n': line = line[:-1]
        line = line.strip()                   #去除前后的空字符，换行符等
        line = line.lower()
        tIndex = line.find("https://www.imdb.com/title")
        if tIndex >= 0 : IMDBLink = line[tIndex:]
        tIndex = line.find("http://www.imdb.com/title")
        if tIndex >= 0 : IMDBLink = line[tIndex:]
        tIndex = line.find("http://movie.douban.com/subject")
        if tIndex >= 0 : DoubanLink = line[tIndex:1]
        tIndex = line.find("https://movie.douban.com/subject")
        if tIndex >= 0 : DoubanLink = line[tIndex:1] 
    gRSSTorrentList[tIndex].DoubanID = GetIDFromLink(DoubanLink,DOUBAN)
    gRSSTorrentList[tIndex].IMDBID   = GetIDFromLink(IMDBLink,IMDB)
    ExecLog("DoubanLink:{} :: IMDBLink:{}".format(DoubanLink,IMDBLink))
    ExecLog("DoubanID:{} :: IMDBID:{}".format(gRSSTorrentList[tIndex].DoubanID,gRSSTorrentList[tIndex].IMDBID))
    if gRSSTorrentList[tIndex].DoubanID == "" and  gRSSTorrentList[tIndex].IMDBID == "" : return 0
    else                                                                                : return 1

def ReadRSSTorrentBackup():
    """
    读取备份目录下的rss.txt，用于恢复RSS记录数据，仅当初始化启动时调用
    """
    
    if not os.path.isfile(RSSTorrentBackupFile): ExecLog(RSSTorrentBackupFile+" does not exist"); return 0
        
    for line in open(RSSTorrentBackupFile):
        RSSName,HASH,Title,Status,DoubanID,IMDBID = line.split('|',5)
        if IMDBID[-1:] == '\n' :  IMDBID = IMDBID[:-1]  #remove '\n'
        gRSSTorrentList.append(RSSTorrent(RSSName,HASH,Title,"",int(Status),DoubanID,IMDBID))
    return 1

def WriteRSSTorrentBackup():
    """
    把当前RSS列表写入备份文件
    """
    
    LogClear(RSSTorrentBackupFile)        
    try : fo = open(RSSTorrentBackupFile,"w")
    except: ErrorLog("Error:open backup file to write："+RSSTorrentBackupFile);  return -1
        
    for i in range(len(gRSSTorrentList)):
        tStr  =     gRSSTorrentList[i].RSSName+'|'
        tStr +=     gRSSTorrentList[i].HASH+'|'
        tStr +=     gRSSTorrentList[i].Title+'|'
        tStr +=     str(gRSSTorrentList[i].Status)+'|'
        tStr +=     gRSSTorrentList[i].DoubanID+'|'
        tStr +=     gRSSTorrentList[i].IMDBID+'\n'
        fo.write(tStr)
  
    fo.close()
    return 1    

def RSSTask(tRSSList=None):
    
    #进行RSS订阅
    if tRSSList == None :
        for tRSS in RSSList1:  RSSRequest(tRSS)
        for tRSS in RSSList2:  RSSRequest(tRSS)
    else:
        for tRSS in tRSSList : RSSRequest(tRSS)
    HandleRSSTorrent()

def HandleRSSTorrent():
    """
    处理gTorrentList列表，进行下载等操作
    """
    global g_DB
    global g_MyCursor

    if len(gRSSTorrentList) == 0 : return True
    
    g_DB = mysql.connector.connect(host="localhost", user=DBUserName, passwd=DBPassword, database=DBName)
    g_MyCursor = g_DB.cursor()
    #检查RSS种子列表
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        DebugLog("connected to QB ")
    except:
        ExecLog("failed to connect QB ")
        g_DB.close()
        return False
        
    BTStat =  os.statvfs(DownloadFolder)
    FreeSize = (BTStat.f_bavail * BTStat.f_frsize) /(1024*1024*1024)
    DebugLog("free size:"+str(FreeSize))
    for i in range(len(gRSSTorrentList)):
        DebugLog("torrent's status is {}:{}".format(gRSSTorrentList[i].Status,gRSSTorrentList[i].Title))
        if gRSSTorrentList[i].Status == TOBEADD:
            try: qb_client.torrents_add(urls=gRSSTorrentList[i].DownloadLink,paused=True)
            except: ExecLog("failed to add torrent:"+gRSSTorrentList[i].Title); continue
            gRSSTorrentList[i].Status = TOBESTART
            ExecLog("success add torrent:"+gRSSTorrentList[i].Title)
            time.sleep(60)         #休眠1分钟，给qb客户端充足的时间下载及加入种子                

        #从qb客户端找到对应的种子
        HASH = gRSSTorrentList[i].HASH
        torrents = qb_client.torrents_info(hashes=HASH)
        if   len(torrents) >= 2 : ErrorLog("find 2+ torrent from hash:"+HASH); continue
        elif len(torrents) == 1 : torrent = torrents[0]; DebugLog("find the torrent:"+torrent.name)
        else: 
            gRSSTorrentList[i].ErrorTimes += 1
            if gRSSTorrentList[i].ErrorTimes >= 3 :
                ErrorLog("find 0 torrent from hash:"+HASH); 
                gRSSTorrentList[i].ToBeDeleted = True
            continue
                

        if gRSSTorrentList[i].Status == TOBESTART:
            Size = torrent.total_size /(1024*1024*1024)
            DebugLog("Size:"+str(Size))
            if FreeSize < Size+1 :ExecLog("diskspace is not enough"); continue
            FreeSize -= Size
            torrent.resume()
            torrent.set_category(category="下载")
            gRSSTorrentList[i].Status = TOBEUPDATE
            ExecLog("start torrent:"+torrent.name)
        
        if gRSSTorrentList[i].Status == TOBEUPDATE:
            update_sql = "UPDATE rss set downloaded=1,TorrentName =%s where id=%s"
            update_val = (torrent.name,HASH)
            try:
                g_MyCursor.execute(update_sql,update_val)
                g_DB.commit()
            except: ExecLog("failed to update rss:"+torrent.name+':'+HASH); continue
            else:   ExecLog("success to update rss:"+torrent.name)
            if gRSSTorrentList[i].DoubanID != "" or gRSSTorrentList[i].IMDBID != "": gRSSTorrentList[i].ToBeDeleted = True
            else: gRSSTorrentList[i].Status = TOBEID
   
        if gRSSTorrentList[i].Status == TOBEID:
            if torrent.progress == 1 :
                if GetIDFromNfo(torrent,i) > 0: 
                    ExecLog("success get id from nfo:"+torrent.name)
                    update_sql = "UPDATE rss set DoubanID=%s,IMDBID =%s where id=%s"
                    update_val = (gRSSTorrentList[i].DoubanID,gRSSTorrentList[i].IMDBID,HASH)
                    try:
                        g_MyCursor.execute(update_sql,update_val)
                        g_DB.commit()
                    except:  ErrorLog("failed to update id:"+torrent.name) 
                    else:   
                        gRSSTorrentList[i].ToBeDeleted = True
                        ExecLog("success to update id:"+torrent.name)
                else  : 
                    gRSSTorrentList[i].ToBeDeleted = True
                    ExecLog("failed  get id from nfo:"+torrent.name)
            else : ExecLog("torrent have not done:"+torrent.name)
    #end for gRSSTorrentList
    i = 0
    while i < len(gRSSTorrentList):
        if gRSSTorrentList[i].ToBeDeleted == True:
            ExecLog("delete from rss torrent list:"+gRSSTorrentList[i].Title)
            del gRSSTorrentList[i]; continue
        i += 1

    g_DB.close()
    #备份文件
    WriteRSSTorrentBackup()
    return True
    
def RSSRequest(tRSS):
    global g_DB
    global g_MyCursor
    
    headers = {    
        'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.82 Safari/537.36'}

    RSSName  = tRSS['Name']
    WaitFree = tRSS['WaitFree']
    url      = tRSS['Url']
    DebugLog("==========begin {}==============".format(RSSName.ljust(10,' ')))
    DebugLog("URL:"+ url)
    try: page = requests.get(url, timeout=60, headers=headers)
    except: ExecLog("failed to requests:"+RSSName); return False 
    page.encoding = 'utf-8'
    page_content = page.text
    soup = BeautifulSoup(page_content, 'lxml-xml')
    items = soup.select('rss > channel > item')
    g_DB = mysql.connector.connect(host="localhost", user=DBUserName, passwd=DBPassword, database=DBName)
    g_MyCursor = g_DB.cursor()
    for i in range(len(items)):
        Title = items[i].title.string
        ID    = items[i].guid.string
        DownloadLink = items[i].enclosure.get('url')
        TorrentID    = GetTorrentID(DownloadLink)
        DebugLog(Title+":"+ID+":"+DownloadLink+":"+TorrentID)

        if RSSName == "HDSky" and Title.find("x265") == -1 : DebugLog("hdsky not x265, ignore it:"+Title); continue
        #if RSSName == "MTeam" and Title.find("x264") >= 0  : DebugLog("mteam x264, ignore it:"+Title); continue

        se_sql = "select Title from rss where RSSName=%s and ID=%s"
        se_val = (RSSName,ID)  
        try: g_MyCursor.execute(se_sql,se_val); tSelectResult = g_MyCursor.fetchall()
        except Exception as err:
            Print(err)
            ErrorLog("failed to select rss:"+RSSName+':'+ID); continue
        if len(tSelectResult) > 0: DebugLog("old rss,ignore it:"+Title); continue

        Type = 0
        Nation = Name = Director = Actors = DoubanScore = DoubanID = DoubanLink = IMDBLink = IMDBScore = IMDBID = ""
        if RSSName == "LeagueHD" or\
           RSSName == "JoyHD"    or\
           RSSName == "HDArea"   or\
           RSSName == "PTSBao"   or\
           RSSName == "BeiTai"   or\
           RSSName[:5] == "HDSky"    or\
           RSSName[:5] == "MTeam"    :
            SummaryStr = items[i].description.string
            SummaryStr = re.sub(u'\u3000',u' ',SummaryStr)
            SummaryStr = re.sub(u'\xa0', u' ', SummaryStr)
            SummaryStr = re.sub('&nbsp;',' ',  SummaryStr)
            SummaryStr = SummaryStr.lower()
            DebugLog(SummaryStr)
                    
            tIndex = SummaryStr.find("豆瓣评分")
            if tIndex >= 0 :
                tempstr = SummaryStr[tIndex+5:tIndex+16]
                tSearch = re.search("[0-9]\.[0-9]",tempstr)
                if tSearch : DoubanScore = tSearch.group()
                else:        DoubanScore = ""
                ExecLog("douban score:"+DoubanScore)
            else: ExecLog("douban score:not find")
            
            tIndex = SummaryStr.find("豆瓣链接")
            if tIndex >= 0 :
                tempstr = SummaryStr[tIndex:]
                tIndex = tempstr.find("href=")
                if tIndex >= 0:
                    tempstr = tempstr[tIndex+6:]
                    tIndex = tempstr.find('\"')
                    if tIndex >= 0 : DoubanLink = tempstr[:tIndex]; DebugLog("douban link:"+DoubanLink)
                    else: ExecLog("douban link:error:not find \"")
                else: ExecLog("douban link:error:not find href=")
            else: ExecLog("douban link:not find")

            if   SummaryStr.find("imdb评分")    >= 0: tIndex = SummaryStr.find("imdb评分")           
            elif SummaryStr.find('imdb.rating') >= 0: tIndex = SummaryStr.find('imdb.rating')
            elif SummaryStr.find('imdb rating') >= 0: tIndex = SummaryStr.find('imdb rating')            
            else: tIndex = -1               
            if tIndex >= 0 :
                tempstr = SummaryStr[tIndex+6:tIndex+36]
                tSearch = re.search("[0-9]\.[0-9]",tempstr)
                if tSearch :  IMDBScore = tSearch.group()
            DoubanID = GetIDFromLink(DoubanLink, DOUBAN)
            ExecLog("imdb score:"+IMDBScore)
            
            if   SummaryStr.find("imdb链接")    >= 0: tIndex = SummaryStr.find("imdb链接")
            elif SummaryStr.find('imdb.link')   >= 0: tIndex = SummaryStr.find("imdb.link")
            elif SummaryStr.find('imdb link')   >= 0: tIndex = SummaryStr.find("imdb link")
            elif SummaryStr.find('imdb url')    >= 0: tIndex = SummaryStr.find('idmb url')           
            else                                    : tIndex = -1            
            if tIndex >= 0 :
                tempstr = SummaryStr[tIndex:tIndex+200]
                tIndex = tempstr.find("href=")
                if tIndex >= 0:
                    tempstr = tempstr[tIndex+6:]
                    tIndex = tempstr.find('\"')
                    if tIndex >= 0 : IMDBLink = tempstr[:tIndex]
                    else:  DebugLog("imdb link:error:not find \"")
                else:
                    tIndex = tempstr.find('http')
                    if tIndex >= 0:
                        tempstr = tempstr[tIndex:]
                        tIndex = tempstr.find('<')
                        if tIndex >= 0 : IMDBLink = tempstr[:tIndex] 
            IMDBID = GetIDFromLink(IMDBLink, IMDB)
            ExecLog("imdb link:"+IMDBLink)

            if   SummaryStr.find("国  家")    >= 0: tIndex = SummaryStr.find("国  家")
            elif SummaryStr.find("产  地")    >= 0: tIndex = SummaryStr.find("产  地")
            else                                  : tIndex = -1
            if tIndex >= 0 :
                Nation = SummaryStr[tIndex+5:tIndex+20]
                if Nation.find('\n') >= 0: Nation = Nation[:Nation.find('\n')]
                if Nation.find('<')  >= 0: Nation = Nation[ :Nation.find('<') ]
                if Nation.find('/')  >= 0: Nation = Nation[ :Nation.find('/') ]
                Nation = Nation.strip()
                if   Nation[-1:] == '国' : Nation = Nation[:-1]  #去除国家最后的国字
                elif Nation == '香港'    : Nation = '港'
                elif Nation == '中国香港': Nation = '港'
                elif Nation == '中国大陆': Nation = '国'
                elif Nation == '中国台湾': Nation = '台'
                elif Nation == '日本'    : Nation = '日'
                else : pass
                ExecLog("Nation:"+Nation)
            else: ExecLog("failed find nation")

            tIndex = SummaryStr.find("类  别") 
            if tIndex >= 0 and SummaryStr[tIndex:tIndex+100].find("纪录") >= 0 : Type = RECORD
            elif SummaryStr.find("集  数") >= 0                                : Type = TV
            else                                                               : Type = MOVIE
            ExecLog("type:"+str(Type))

            if Nation == '港' or Nation == '国' or Nation == '台' : tIndex = SummaryStr.find("片  名")
            else                                                  : tIndex = SummaryStr.find("译  名")
            if tIndex >= 0 :
                Name = SummaryStr[tIndex+5:tIndex+100]
                if   Name.find("/")  >= 0 : Name = (Name[ :Name.find("/") ]).strip() 
                elif Name.find("<")  >= 0 : Name = (Name[ :Name.find("<") ]).strip() 
                elif Name.find('\n') >= 0 : Name = (Name[ :Name.find('\n') ]).strip()
                else: ExecLog("failed find name"); Name = ""
            else: ExecLog("failed find name"); Name = ""
            ExecLog("name:"+Name)
            if Name.find('<') >= 0 : Name = Name[:Name.find('<')]
            ExecLog("name:"+Name)
            
            tIndex = SummaryStr.find("导  演")
            if tIndex >= 0 :
                Director = SummaryStr[tIndex+5:tIndex+100]
                tEndIndex = Director.find('\n')
                if tEndIndex >= 0 : Director = Director[:tEndIndex]
                else : Director = ""
                Director = (Director[ :Director.find('<') ]).strip()
            else :Director = ""
            ExecLog("director:"+Director)
        #end if RSSName ==
        
        #加入待完成的RSSTorrent列表
        Title = Title.replace('|',',')   #避免Title中出现|分隔符
        if not WaitFree: gRSSTorrentList.append(RSSTorrent(RSSName,ID,Title,DownloadLink,TOBEADD,DoubanID,IMDBID))
        
        tCurrentTime = datetime.datetime.now()
        AddDate = tCurrentTime.strftime('%Y-%m-%d')
        ExecLog("new rss: "+Title)
        in_sql = "INSERT INTO rss \
                (RSSName, ID, Title, DownloadLink, TorrentID, DoubanScore, DoubanLink, DoubanID, IMDBScore, IMDBLink, IMDBID, Type, Nation, Name, Director, AddDate) \
          VALUES(%s,      %s, %s   , %s          , %s       , %s         , %s        , %s      , %s       , %s      , %s    , %s  , %s    , %s  , %s      , %s  )" 
        in_val= (RSSName, ID, Title, DownloadLink, TorrentID, DoubanScore, DoubanLink, DoubanID, IMDBScore, IMDBLink, IMDBID, Type, Nation, Name, Director, AddDate)
        DebugLog("{}::{}::{}::{}::{}::{}::{}::{}".format(RSSName,ID,Title,DownloadLink,DoubanScore,DoubanLink,IMDBScore,IMDBLink))
        try:g_MyCursor.execute(in_sql,in_val);g_DB.commit()
        except Exception as err: 
            Print(err)
            ExecLog("insert error:"+Title)
        else:ExecLog("success insert rss table")
    #end for Items
    g_DB.close()
    return True
    
def DownloadFree(RSSName):
    Page = mteam_free.NexusPage()
    TaskList = Page.find_free()
    if len(TaskList) == 0 : return True

    g_DB = mysql.connector.connect(host="localhost", user=DBUserName, passwd=DBPassword, database=DBName)
    g_MyCursor = g_DB.cursor()

    for tTask in TaskList:
        if tTask[0] == False: continue
        TorrentID = tTask[1]
        sel_sql = "select ID,title,downloadlink,DoubanID,IMDBID,Downloaded from rss where rssname=%s and torrentid=%s"
        sel_val = (RSSName,TorrentID)
        g_MyCursor.execute(sel_sql,sel_val)
        SelectResult = g_MyCursor.fetchall()
        if len(SelectResult) != 1: ExecLog("failed to find torrentid:"+TorrentID); continue
        ID           = SelectResult[0][0]
        Title        = SelectResult[0][1]
        DownloadLink = SelectResult[0][2]
        DoubanID     = SelectResult[0][3]
        IMDBID       = SelectResult[0][4]
        Downloaded   = SelectResult[0][5]
        if Downloaded == 1 : DebugLog("torrentID have been downloaded:"+TorrentID+"::"+Title); continue
        gRSSTorrentList.append(RSSTorrent(RSSName,ID,Title,DownloadLink,TOBEADD,DoubanID,IMDBID))
        ExecLog("find a free torrent:"+Title)

    g_DB.close()
    HandleRSSTorrent()
    return True



def BackupTorrentFile():
    """
    把QB和TR的torrents备份到相应目录
    """

    global QBBackupDir
    global TRBackupDir
    global QBTorrentsBackupDir
    global TRTorrentsBackupDir

    if QBBackupDir[-1:] != '/' : QBBackupDir = QBBackupDir+'/'
    if TRBackupDir[-1:] != '/' : TRBackupDir = TRBackupDir+'/'
    if QBTorrentsBackupDir[-1:] != '/' : QBTorrentsBackupDir = QBTorrentsBackupDir+'/'
    if TRTorrentsBackupDir[-1:] != '/' : TRTorrentsBackupDir = TRTorrentsBackupDir+'/'

    QBCopyCommand = "cp -n "+QBBackupDir+"* "+QBTorrentsBackupDir
    #ExecLog("exec:"+QBCopyCommand)
    if os.system(QBCopyCommand) == 0 : ExecLog ("success exec:"+QBCopyCommand)
    else : ExecLog("failed to exec:"+QBCopyCommand); return False

    TRCopyCommand1 = "cp -n "+TRBackupDir+"torrents/* "+TRTorrentsBackupDir
    #ExecLog("exec:"+TRCopyCommand1)
    if os.system(TRCopyCommand1) == 0 : ExecLog ("success exec:"+TRCopyCommand1)
    else : ExecLog("failed to exec:"+TRCopyCommand1); return False
    TRCopyCommand2 = "cp -n "+TRBackupDir+"resume/* "+TRTorrentsBackupDir
    #ExecLog("exec:"+TRCopyCommand2)
    if os.system(TRCopyCommand2) == 0 : ExecLog ("success exec:"+TRCopyCommand2)
    else : ExecLog("failed to exec:"+TRCopyCommand2); return False
 
def HandleTask(Request):
    ExecLog("accept request:"+Request)
    RequestList = Request.split()
    Task = RequestList[0].lower(); del RequestList[0]
    if   Task == 'checkdisk': 
        if len(RequestList) > 0 : CheckDisk(RequestList)
        else                    : CheckDisk(CheckDiskList)
    elif Task == 'rss'      : 
        if len(RequestList) > 0 : 
            for RSSName in RequestList: 
                for tRSS in RSSList1:
                    if tRSS['Name'].lower() == RSSName.lower(): RSSTask([tRSS])
                for tRSS in RSSList2:
                    if tRSS['Name'].lower() == RSSName.lower(): RSSTask([tRSS])
        else                    : RSSTask()
    elif Task == 'free'     :
        if len(RequestList) > 0 : DownloadFree(RequestList[0])
        else                    : DownloadFree('MTeam')
    elif Task == 'checkqb'      : CheckTorrents(QB)
    elif Task == 'checktr'      : CheckTorrents(TR)
    elif Task == 'backuptorrent': BackupTorrentFile()
    elif Task == 'keep'         : KeepTorrents( CheckDisk(RequestList) )
    else                        : ExecLog("unknown request task:"+Task) ; return "unknown request task"     
    
    return "completed"

def KeepTorrents(tDirNameList):
    """
    输入:待进行辅种的目录列表
    1、查找movies表，获取下载链接及hash
    2、如果下载链接不唯恐，就取下载链接，否则通过hash值去种子备份目录寻找种子文件
    3、加入qb，设置分类为'转移',跳检，不创建子文件夹
    """
    try:
        tr_client = transmissionrpc.Client(TR_IP, port=TR_PORT,user=TR_USER,password=TR_PWD)
    except Exception as err:
        print(err)
        ErrorLog("failed to connect tr")
        return False

    g_DB = mysql.connector.connect( host="localhost",  user=DBUserName,  passwd=DBPassword, database=DBName)
    g_MyCursor = g_DB.cursor()
    for tDirName in tDirNameList:
        ExecLog("begin to keep torrent:"+tDirName['DirPath']+tDirName['DirName'])
        tMovie = movie.Movie(tDirName['DirPath'],tDirName['DirName'])
        if tMovie.CheckDirName() == 0 :
            ExecLog("failed to checkdirname:"+tMovie.DirName)
            continue
        sel_sql = 'select downloadlink,hash from movies where number = %s and copy = %s'
        sel_val = (tMovie.Number,tMovie.Copy)
        g_MyCursor.execute(sel_sql,sel_val)
        SelectResult = g_MyCursor.fetchall()
        if len(SelectResult) != 1: ExecLog("failed to select from movies:{}::{}".format(tMovie.Number,tMovie.Copy)); continue
        DownloadLink = SelectResult[0][0]
        HASH         = SelectResult[0][1]
        if DownloadLink == "" :
            if HASH != "":
                #到QB目录查找文件
                TorrentFile = ""
                if os.path.isfile( os.path.join(QBTorrentsBackupDir, HASH+'.torrent') ) : 
                    TorrentFile = os.path.join(QBTorrentsBackupDir, HASH+'.torrent')
                    DebugLog("find torrent file:"+TorrentFile)
                else :
                    #到TR目录查找文件
                    IsFindTorrentFile = False
                    for tFile in os.listdir(TRTorrentsBackupDir):
                        if tFile[-24:] == HASH[:16]+'.torrent': IsFindTorrentFile = True; break
                    if IsFindTorrentFile == True : 
                        TorrentFile = tFile
                        DebugLog("find torrent file:"+TorrentFile)
                    else:
                        ExecLog("failed to find torrent file:"+HASH); continue
            else : ExecLog("downloadlink and hash is null:"+tDirName['DirName']); continue

        try:
            if DownloadLink != "": tr_torrent = tr_client.add_torrent(DownloadLink,download_dir=TRSeedFolderList[0],paused=True)
            else: tr_torrent = tr_client.add_torrent(torrent=TorrentFile,download_dir=TRSeedFolderList[0],paused=True)
        except Exception as err:
            Print(err)
            ErrorLog("failed to add torrent:"+TorrentFile+"::"+DownloadLink)
            continue
        else:
            ExecLog("success add torrent to tr")
        
        tLink = os.path.join(TRSeedFolderList[0],tr_torrent.name) 
        tFullPathDirName = os.path.join(tDirName['DirPath']+tDirName['DirName'])
        if os.path.exists(tLink) : os.remove(tLink)
        try:    
            os.symlink(tFullPathDirName,tLink)
        except:
            ErrorLog("failed create link:ln -s "+tFullPathDirName+" "+tLink)
        else: ExecLog("create link: ln -s "+tFullPathDirName+" "+tLink)

    #把新加入的种子加入列表
    CheckTorrents(TR)
    
if __name__ == '__main__' :

    tCurrentTime = datetime.datetime.now()
    gToDay = tCurrentTime.strftime('%Y-%m-%d')
    
    ExecLog("Begin ReadPTBackup from "+TorrentListBackup)
    if ReadPTBackup() == 1:
        ExecLog("success ReadPTBackup. set gLastCheckDate="+gLastCheckDate)
        ExecLog(str(len(gTorrentList)).zfill(4)+" torrents readed.")
    if ReadIgnoreList() == 1:
        ExecLog("success ReadIgnoreList:")
        #for tFile in gPTIgnoreList : DebugLog(tFile['Path']+"::"+tFile['Name'])      
    if ReadTrackerBackup() == 1:  ExecLog("success ReadTrackerBackup:"+TrackerListBackup)
    if ReadRSSTorrentBackup() > 0: ExecLog("success read rss torrent backup:"+RSSTorrentBackupFile)
    
    try:
        Socket = socket.socket()
        HOST = socket.gethostname()
        Socket.bind((HOST,PTPORT))
        Socket.listen(5)
        Socket.settimeout(60)
    except Exception as err:
        Print("fail to make socket")
        Print(err)
        exit()

    #初始化建立gTorrentList
    tTRReturn = CheckTorrents(TR)
    tQBReturn = CheckTorrents(QB)

    LoopTimes = 0
    while True:
        LoopTimes += 1
        Print("loop times :"+str(LoopTimes%120) )
        tCurrentTime = datetime.datetime.now()
        gToDay = tCurrentTime.strftime('%Y-%m-%d')
        if gToDay != gLastCheckDate :      gIsNewDay = True
        else:                              gIsNewDay = False

        #执行定时任务
        #RSSTask()
        #CheckTorrents(QB)
        #gIsNewDay = True
        if LoopTimes % 8  == 0 : RSSTask(RSSList1)
        if LoopTimes % 60 == 0 : RSSTask(RSSList2)
        if LoopTimes % 16 == 0 : DownloadFree('MTeam')
        if LoopTimes % 30 == 0 : CheckTorrents(QB)
        if gIsNewDay : 
            CheckTorrents(QB)
            CheckTorrents(TR)
            CheckDisk(CheckDiskList)
            TrackerData()
            BackupTorrentFile()
            #一月备份一次qb，tr,data
            if gToDay[8:10] == '01' : os.system("/root/backup.sh"); ExecLog("exec:/root/backup.sh")
                
        """
        #转移QB的种子（停止状态，分类为保种）到TR做种
        tNumber = MoveTorrents()
        if tNumber > 0 : DebugLog(str(tNumber)+" torrents moved")
        
        #将QB分类为save的种子保存到tobe目录
        SaveTorrents()
        """

        #检查一下内存占用
        tMem = psutil.virtual_memory()
        DebugLog("memory percent used:"+str(tMem.percent))
        if tMem.percent >= 95: ExecLog("memory percent used:"+str(tMem.percent)); RestartQB()
                
        
        gLastCheckDate = tCurrentTime.strftime("%Y-%m-%d")
        DebugLog("update gLastCheckDate="+gLastCheckDate)        

        #监听Client是否有任务请求
        #Print("begin accept")
        try:
            Connect,Address = Socket.accept()
            Print(Address)
        except socket.timeout:
            #Print("accept timeout")
            continue
        except Exception as err:
            ErrorLog("accept error:")
            Print(err)
            continue

        #接受请求
        Print("begin recv") 
        try:
            data = Connect.recv(1024)
        except socket.timeout:
            Print("recv timeout")
            continue
        except Exception as err:
            ErrorLog("recv error")
            Print(err)
        else:
            Request = str(data, encoding="utf-8")
            Print("recv success:"+Request)

        Reply = HandleTask(Request)
        Print("begin send")
        try:
            Connect.send( bytes(Reply,encoding="utf-8") )
        except socket.timeout:
            Print("send timeout")
            continue
        except Exception as err:
            Print(err)
            continue
        else:
            Print("send success:"+Reply)

        Connect.close()

        

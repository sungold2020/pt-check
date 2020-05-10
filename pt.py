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
"""
一、读取备份种子数据，建立种子列表
备份文件在TorrentListBackup
二、每隔半个小时执行任务：访问QB和TR(QB/TR的用户密码等写在程序），获取种子列表，逐个进行分析
1、对于下载保存路径不在RootFolderList中的种子，报错，暂停
2、检查文件是否存在（半小时仅检查第一个文件，隔天完整检查一次），文件不存在就报错，暂停
3、新的一天，记录当天的种子上传量（绝对值），开始统计NUMBEROFDAYS内的相对下载量，
    如果连续NUMBEROFDAYS内上传量低于阈值UPLOADTHRESHOLD，就认为最近低上传。而且不属于保种的种子就暂停。如何判断是否属于保种呢？
    对于QB：如果种子分类不属于'保种'的，就暂停种子。
    对于TR：如果报错路径不在TRSeedFolderList，就暂停种子
4、为了方便QB的WEB页浏览，我根据TRACKER进行了标签设置，这样如果可以自动设置标签（我目前区分为frds/mteam/other）
5、最后更新列表并写入备份文件

修订记录：
2020-03-15 12:00：V2.0：
    1、重新用transmissionrpc，python-qbittorrent接口编写。
    2、封装了两个客户端的不同，简化代码
    3、重新整理了日志
    不足：1、不支持QB的tags设定
2020-03-16:V2.1，
    1,判断IsLowUpload后，需要判断种子状态，对于已经为停止/暂停状态的种子不做处理。
    2,修订原来TRSEEDPATH仅为单一目录，更改为目录列表：TRSeedFolerList，
    3、增加一个立即执行的入口，pt.py now就会立即执行一次检查，仅检查种子并处理，但不写入backup文件
2020-03-17：V2.2
    1,GetDirName, files == 1, bug

2020-03-18：V2.3
    1、把种子信息备份文件TorrentListBackup，增加保留当月及上月的备份文件。后缀为"."+"日期"
V3 ：
    1、增加MoveTorrents，从QB状态为停止，分类为“保种”的种子转移到TR进行做种
    2、修订checkdisk的入口
    
V4
1、增加QB的内存泄露功能，当内存占用超过95%后，重启QB
V4.1
1、增加一个各个网站的上传量统计
2、增加一个统计各网站几天内无上传量的统计

2020-04-24：V5
1、增加一个保存功能，
"""

 
#运行设置############################################################################
#日志文件
DebugLogFile = "log/pt.log"             #日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/pt.error"             #错误日志
movie.Movie.ErrorLogFile  =  ErrorLogFile
movie.Movie.ExecLogFile  =  DebugLogFile
movie.Movie.DebugLogFile  =  "log/pt.debug"
movie.Movie.ToBeExecDirName  =  True
movie.Movie.ToBeExecRmdir  =  False
movie.Movie.DBUserName = "dummy"
movie.Movie.DBPassword = ""

#TR/QB的连接设置    
TR_IP = "localhost"
TR_PORT = 9091
TR_USER = ''
TR_PWD  = ''
QB_IPPORT = 'localhost:8989'
QB_USER = ''
QB_PWD =  ''

#连续NUMBEROFDAYS上传低于UPLOADTHRESHOLD，并且类别不属于'保种'的种子，会自动停止。
#QB：把保种的种子分类设为"保种"，就不会停止
#TR：因为不支持分类，通过制定文件夹方式来判断，如果保存路径在TRSeedFolderList中，认为属于“保种”
NUMBEROFDAYS = 3                           #连续多少天低于阈值
UPLOADTHRESHOLD = 200000000                 #阈值，单位Bytes
ToBePath = "/media/root/BT/tobe/"           #低上传的种子把文件夹移到该目录待处理
#TR的保种路径，保存路径属于这个列表的就认为是保种,，如果类别为保种的话，就不会检查是否属于lowupload
TRSeedFolderList = ["/media/root/BT/keep" ,"/root/e52/books"]
#或者手工维护一个TR分类清单，从转移保种的会自动加入。
TRCategoryFile = "data/tr_category.txt"

#下载保存路径的列表，不在这个列表中的种子会报错.其中第一个路径用于创建符号链接来转移QB种子
RootFolderList = [  "/sg3t",\
                    "/media/root/wd4t",\
                    "/media/root/BT/keep",\
                    "/media/root/BT/temp",\
                    "/media/root/BT/music",\
                    "/media/root/BT/movies",\
                    "/root/e52/books" ]
TorrentListBackup = "data/pt.txt"  #种子信息备份目录（重要的是每天的上传量）

#配置自己要检查的磁盘/保存路径，看下面是否有文件夹/文件已经不在种子列表，这样就可以转移或者删除了。
CheckDiskList = [ "/media/root/wd4t","/media/root/BT/movies"]
#如果有一些文件夹/文件不想总是被检查，可以建一个忽略清单
IgnoreListFile = "data/ignore.txt"

#从QB转移到TR做种：定期检查QB状态为停止且分类为‘保种’的会转移到TR做种，转移成功后，QB种子分类会设置为'转移'
#QB的备份目录BT_backup，我的运行环境目录如下，如有不同请搜索qbittorrent在不同OS下的配置
QBBackupDir = "/root/.local/share/data/qBittorrent/BT_backup"
#转移做种以后，把种子文件和快速恢复文件转移到QBTorrentsBackupDir目录进行保存，以备需要
QBTorrentsBackupDir = "data/qb_backup"   

FRDSDataList   = []
MTeamDataList  = []
HDHomeDataList = []
BeiTaiDataList = []
JoyHDDataList  = []
SoulVoiceDataList = []
PTHomeDataList = []
PTSBaoDataList = []
LeagueHDDataList = []
HDAreaDataList = []
AVGVDataList   = []
HDSkyDataList   = []
TrackerListBackup = "data/tracker.txt"               
#运行设置结束#################################################################################

#程序易读性用，请勿修改
STOP    = "STOP"
GOING   = "GOING"
ERROR   = "ERROR"
TR       = "TR"
QB       = "QB"
CHECKERROR = -1
NOCHANGE =  0
UPDATED = 1
ADDED = 2
LOWUPLOAD = 3

#可变全局变量
global gPTIgnoreList             #checkdisk的忽略文件夹/名清单
global gTorrentList              #种子信息清单
global gTRCategoryList           #给TR用的分类列表，TR不支持分类，程序需要自己创建分类，文件保存在tr_category.txt
global LastCheckDate 
global gIsNewDay
global gToday
global gIsMove 
gPTIgnoreList = []
gTorrentList = []
gTRCategoryList = []
gTRCategoryUpdate = False
gLastCheckDate = "1970-01-01"
gIsNewDay = False
gToday = "1970-01-01"
gIsMove = False

#记录日志用的函数############################################################
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
    
def ErrorLog(Str):
    print(Str)
    DebugLog(Str)
    Log(ErrorLogFile,Str)
################################################################################   



def IsSubDir(SrcDir,DestDirList):
    """
    判断SrcDir是否属于DestDirList中给出的路径的子文件夹
    举例：DestDirList中假设有/e52/books，则SrcDir=/e52/books/学习资料，它就属于其中的子文件夹
    
    返回值：属于就返回1，不属于则返回0
    """

    if SrcDir[-1:] == '/' : SrcDir = SrcDir[:-1] #移除最后一个'/'
    i = 0
    while i< len(DestDirList):
        tLenDest = len(DestDirList[i])
        tDestDir = DestDirList[i]
        if tDestDir[-1:] == '/' : tDestDir = tDestDir[:-1]  #移除最后一个 '/'
        if len(SrcDir) < tLenDest :  i += 1; continue
        if SrcDir[:tLenDest] == tDestDir :  return True
        i += 1
    return False


class TorrentInfo :
    def __init__(self,Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData,Tracker=""):
        
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
        i = 0; 
        while i < len(files) :
            if self.Client == TR :
                Name = files[i]['name']  
                Size = files[i]['size']
                Done = (files[i]['completed']/files[i]['size'])*100
            else:
                Name = files[i].name
                Size = files[i].size
                Done = files[i].progress*100
            #Done = int (files[i]['completed']/Size * 100)    
            self.FileName.append( {'Name':Name,'Size':Size,'Done':Done} )
            i += 1
        
        #首先找该种子是否存在
        tNoOfTheList = FindTorrent(self.Client,self.HASH)
        if tNoOfTheList == -1 : #没找到，说明是新种子，加入TorrentList
            gTorrentList.append(self)
            DebugLog("add torrent, name="+self.Name)
            return ADDED
        gTorrentList[tNoOfTheList].Checked = 1
        
        #获取RootFolder和DirName
        if self.GetDirName() == -1:
            return CHECKERROR

        #检查文件是否存在，一天完整检查一次，否则仅检查分类不属于保种的第一个文件
        if self.Done == 100 :
            if gIsNewDay == True :
                i = 0 
                while i < len(self.FileName) :
                    if self.FileName[i]['Done'] != 100: continue
                    tFullFileName = os.path.join(self.SavedPath, self.FileName[i]['Name'])
                    if not os.path.isfile(tFullFileName):
                        ErrorLog(tFullFileName+" does not exist")
                        return CHECKERROR
                    if self.FileName[i]['Size'] != os.path.getsize(tFullFileName) :
                        ErrorLog(tFullFileName+" file size error. torrent size:"+str(self.FileName[i]['Size']))
                        return CHECKERROR
                    i+=1
            else: #不是新的一天，对于非转移/保种/低上传分类的种子，仅检查第一个下载完成的文件是否存在
                if self.Client == QB and (self.Category ==  '保种' or self.Category == '转移' or self.Category == '低上传') : pass
                elif  self.Client == TR and (self.Category == '保种' or IsSubDir(self.SavedPath,TRSeedFolderList) or self.Category == '低上传') : pass
                else :
                    #DebugLog("check torrent file:"+self.Name+"::"+self.SavedPath)
                    i = 0
                    while i < len(self.FileName):
                        if self.FileName[i]['Done'] != 100: continue
                        tFullFileName = os.path.join(self.SavedPath, self.FileName[0]['Name'])
                        if not os.path.isfile(tFullFileName) :
                            ErrorLog(tFullFileName+" does not exist")
                            return CHECKERROR
                        else: break
                        i += 1

        if self.Status == STOP and self.Category == '低上传':
            tFullPath = os.path.join(self.RootFolder,self.DirName)
            if os.path.exists(tFullPath):
                DebugLog(tFullPath+" exists, begin mv to "+ToBePath)
                try:
                    shutil.move(tFullPath, ToBePath)
                except:
                    ErrorLog("failed mv dir :"+tFullPath)
                else:
                    DebugLog("lowupload, so mv dir "+tFullPath)
            #DebugLog("lowupload, so mv dir "+tFullPath)
            
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
        
        if gIsNewDay == True :   #新的一天，更新记录每天的上传量（绝对值）
            gTorrentList[tNoOfTheList].DateData.append(self.DateData[0])
            if len(gTorrentList[tNoOfTheList].DateData) >= NUMBEROFDAYS+3: del gTorrentList[tNoOfTheList].DateData[0] #删除前面旧的数据
            
            if IsLowUpload(gTorrentList[tNoOfTheList].DateData) :
                if self.Status != STOP :
                    if gTorrentList[tNoOfTheList].Client == QB :
                        if gTorrentList[tNoOfTheList].Category == '保种' or\
                           gTorrentList[tNoOfTheList].Category == '转移' or\
                           gTorrentList[tNoOfTheList].Category == '低上传': return UPDATED 
                        else : return LOWUPLOAD
                    else:
                        if gTorrentList[tNoOfTheList].Category == '保种' or \
                           gTorrentList[tNoOfTheList].Category == '低上传' or\
                           IsSubDir(gTorrentList[tNoOfTheList].SavedPath,TRSeedFolderList) == True :  return UPDATED
                        else :   return LOWUPLOAD
                return UPDATED
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
        self.IsRootFolder = True; tSubDirName = ""; i = 0   
        while i < len(self.FileName) :
            tIndex = (self.FileName[i]['Name']).find('/')
            if tIndex == -1 :  self.IsRootFolder = False; break
            if tSubDirName == "":
                tSubDirName = (self.FileName[i]['Name'])[0:tIndex]
            else :
                if (self.FileName[i]['Name'])[0:tIndex] != tSubDirName : self.IsRootFolder = False; break
            i += 1           
               
        self.SavedPath = self.SavedPath.strip()
        if self.SavedPath[-1:] == '/' : self.SavedPath = self.SavedPath[:-1] #去掉最后一个字符'/'
        
        tSplitPath = self.SavedPath.split('/')
        #print(tSplitPath)
        i = 0 ; tIndex = 0;  tPath = "/"
        while i < len(tSplitPath) :
            tPath = os.path.join(tPath,tSplitPath[i])
            #print(tPath)
            if tPath in RootFolderList : 
                #print("find at:"+str(i))
                tIndex = i; break
            i += 1
        
        if tIndex == 0 : #SavedPath不在RootFolderList中
            #print(RootFolderList)
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
        Category = FindTRCategory(HASH)
        Tags = ""
        SavedPath = torrent.downloadDir
        AddDateTime = time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime(torrent.addedDate) ) 
        Tracker = torrent.trackers[0]['announce']
        DateData = [] ;  DateData.append({'Date':gToday,'Data':torrent.uploadedEver})  
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
        DateData = [] ;  DateData.append({'Date':gToday,'Data':torrent.uploaded})   

    return  TorrentInfo(Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData,Tracker)
    
def IsLowUpload(DateData):
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
        if tDeltaData < UPLOADTHRESHOLD :    tDays += 1
        else:    return False  #有一天高于阈值就退出
        i -= 1
    
    #运行到这，tDays应该就等于NUMBEROFDAYS,不过代码还是加一个判断
    if tDays >= NUMBEROFDAYS : return True
    else : return False
        
def FindTorrent(Client,HASH):
    """
    根据HASH寻找TorrentList，如果找到就返回序号，否则返回-1
    """
    global gTorrentList

    i = 0
    while i < len(gTorrentList) :
        if HASH == gTorrentList[i].HASH and gTorrentList[i].Client == Client :  return i
        i+=1

    return -1   
    
def ReadPTBackup():
    """
    读取备份目录下的pt.txt，用于恢复种子记录数据，仅当初始化启动时调用
    """
    
    global gTorrentList
    global gLastCheckDate
    
    #
    if not os.path.isfile(TorrentListBackup):
        DebugLog(TorrentListBackup+" does not exist")
        return 0
        
    for line in open(TorrentListBackup):
        Client,HASH,Name,tDoneStr,Status,Category,Tags,SavedPath,AddDateTime,RootFolder,DirName,tDateDataStr = line.split('|',11)
        Done = int(float(tDoneStr))
        if tDateDataStr [-1:] == '\n' :  tDateDataStr = tDateDataStr[:-1]  #remove '\n'
        #DebugLog("DateData="+tDateDataStr)
        tDateDataList = tDateDataStr.split(',')
        #DebugLog (str(len(tDateDataList))+tDateDataList[0])
        i = 0 ; DateData = []
        while i < len(tDateDataList) :
            if tDateDataList[i] == "" :  break      #最后一个可能为空就退出循环
            tDate = (tDateDataList[i])[:10]
            tData = int( (tDateDataList[i])[11:] )
            DateData.append({'Date':tDate,'Data':tData})
            i += 1
        gTorrentList.append(TorrentInfo(Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData))
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
        tThisMonth = gToday[0:7] ; tThisYear = gToday[0:4]
        if tThisMonth[5:7] == "01" : 
            tLastMonth = str(int(tThisYear)-1)+"-"+"12"      
        else : 
            tLastMonth = tThisYear+"-"+str(int(tThisMonth[5:7])-1).zfill(2)
        
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
    else :
        LogClear(TorrentListBackup)        

    try :
        fo = open(TorrentListBackup,"w")
    except:
        ErrorLog("Error:open ptbackup file to write："+TorrentListBackup)
        return -1
        
    i = 0; tLength = len(gTorrentList)
    while i < tLength :
        j = 0 ; tDateDataListStr = ""
        while j < len(gTorrentList[i].DateData):        
            tDateDataStr = gTorrentList[i].DateData[j]['Date']+":" + str(gTorrentList[i].DateData[j]['Data'])
            tDateDataListStr += tDateDataStr+','
            j += 1
        if tDateDataListStr[-1:] == ',' : tDateDataListStr = tDateDataListStr[:-1] #去掉最后一个','
        
        #DebugLog(tDateDataListStr)
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
        i += 1   
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
    global gTRCategoryUpdate
    
    tNumberOfAdded = 0
    tNumberOfDeleted = 0
    tNumberOfUpdated = 0
    tNumberOfPaused = 0 
    tNumberOfError = 0
    tNumberOfNoChange = 0
    tNumberOfTorrent = 0

    #先把检查标志复位
    i = 0; tLength = len(gTorrentList)
    while i < tLength :
        if gTorrentList[i].Client == Client : gTorrentList[i].Checked = 0
        i += 1
   
    #连接Client并获取TorrentList列表
    try:
        if Client == TR :
            tr_client = transmissionrpc.Client(TR_IP, port=TR_PORT,user=TR_USER,password=TR_PWD)
            torrents = tr_client.get_torrents()
        else :
            #qb_client = qbittorrent.Client(QB_IPPORT)
            #qb_client.login(QB_USER, QB_PWD)
            #torrents = qb_client.torrents()
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
        
        #对于QB检查并设置标签，frds,other
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
            DebugLog("stop torrent for error, name="+torrent.name)
        if tReturn == LOWUPLOAD : 
            if Client == TR:  
                torrent.stop()
                UpdateTRCategory(torrent.hashString,'低上传',torrent.name)
                gTRCategoryUpdate = True
            else :            
                torrent.pause()
                torrent.set_category('低上传')
            DebugLog("stop torrent for low upload, name="+torrent.name)
                
        tNumberOfTorrent += 1
    #end for tr torrent 
    
    #最后，找出没有Checked标志的种子列表，进行删除操作。
    i = 0; tLength = len(gTorrentList)
    while i < len(gTorrentList) :
        if gTorrentList[i].Checked == 0 and gTorrentList[i].Client == Client:
            tNumberOfDeleted += 1
            DebugLog("del torrent, name="+gTorrentList[i].Name)
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
        #print("find file:"+IgnoreListFile)
        for line in open(IgnoreListFile):
            Path,Name = line.split('|',1)
            Path = Path.strip(); Name = Name.strip()
            if Name[-1:] == '\n' : Name = Name[:-1]
            gPTIgnoreList.append({'Path':Path,'Name':Name})
            print(gPTIgnoreList[-1]['Path']+"::"+gPTIgnoreList[-1]['Name'])
        return 1
    else :
        print("not find file:"+IgnoreListFile)
        DebugLog(IgnoreListFile+" is not exist")
        return 0

def InPTIgnoreList(SavedPath,DirName) :

    if SavedPath[-1:] == '/' : SavedPath = SavedPath[:-1]
    i = 0
    while i < len(gPTIgnoreList) :
        if (gPTIgnoreList[i])['Path'] == SavedPath and (gPTIgnoreList[i])['Name'] == DirName:
            return True
        i += 1
    return False

def InTorrentList(SavedPath,DirName):
    """
    判断SavedPath+DirName在不在TorrentList
    """
    i = 0 
    while i < len(gTorrentList) :
        tSrcDirName = os.path.join(SavedPath,DirName)
        tDestDirName = os.path.join(gTorrentList[i].RootFolder,gTorrentList[i].DirName)
        if os.path.realpath(tSrcDirName) == os.path.realpath(tDestDirName): return True
        i += 1
    return False
#end def InTorrentList
    
def CheckDisk(DiskPath):
    """
    对Path下的目录及文件逐个对比TorrentList，并进行标记。
    """

    DebugLog("begin check:"+DiskPath)
    for file in os.listdir(DiskPath):        
        fullpathfile = os.path.join(DiskPath,file)
        #DebugLog("check:"+fullpathfile)
        if os.path.isdir(fullpathfile) or os.path.isfile(fullpathfile):        
            #一些特殊文件夹忽略
            if file == 'lost+found' or file[0:6] == '.Trash' :
                DebugLog ("ignore some dir:"+file)
                continue 
            
            if InPTIgnoreList(DiskPath,file):
                DebugLog ("in Ignore List:"+DiskPath+"::"+file)
                continue

            if InTorrentList(DiskPath,file) : pass #DebugLog(file+"::find in torrent list:")
            else :                            ErrorLog(file+"::not find in torrent list:")
        else :
            DebugLog("Error：not file or dir")
#end def CheckDisk

def ReadTRCategory():
    """
    读取TRCategory分类信息，可以手工维护
    """
    global gTRCategoryList
    if os.path.isfile(TRCategoryFile):
        print("find file:"+TRCategoryFile)
        for line in open(TRCategoryFile):
            #print(line)
            Category,Name,HASH = line.split('|',2)
            if HASH[-1:] == '\n' : HASH = HASH[:-1]  #去除最后一个'/n'
            #print(HASH)
            gTRCategoryList.append({'Category':Category,'Name':Name,'HASH':HASH})
        return 1
    else :
        print("not find file:"+TRCategoryFile)
        DebugLog(TRCategoryFile+" is not exist")
        return 0
   
def WriteTRCategory():
    """
    把TR的分类信息写入备份文件
    """
    
    #删除不存在的torrent
    i = 0
    while i < len(gTRCategoryList) :
        if FindTorrent(TR,gTRCategoryList[i]['HASH']) == -1 : del gTRCategoryList[i]; continue
        i += 1    
    
    LogClear(TRCategoryFile)        
    try :
        fo = open(TRCategoryFile,"w")
    except:
        ErrorLog("failed to open："+TRCategoryFile)
        return -1
        
    i = 0; tLength = len(gTRCategoryList)
    while i < tLength :
        tStr = gTRCategoryList[i]['Category']+'|'+gTRCategoryList[i]['Name']+'|'+gTRCategoryList[i]['HASH']+'\n'
        fo.write(tStr)
        i += 1   
    fo.close()
    
    DebugLog(str(len(gTRCategoryList))+"category records writed to:"+TRCategoryFile)
    return 1

def FindTRCategory(HASH):
    """
    """
    for tCategory in gTRCategoryList:
        if tCategory['HASH'] == HASH : return tCategory['Category']
    return ""
def UpdateTRCategory(HASH,Category,Name):
    i = 0
    while i < len(gTRCategoryList):
        if gTRCategoryList[i]['HASH'] == HASH :
            gTRCategoryList[i]['Category'] = Category
            return 1
        i += 1
    gTRCategoryList.append({'Category':Category,'Name':Name,'HASH':HASH})
    return 0

def MoveTorrents():
    """
    将QB中类别为'保种'，状态为pause的种子移到tr去保种
    返回值：转移保种的种子数
    
    首先连接到qb/tr客户端
    1、逐个匹配gTorrentList中符合条件的种子
    2、备份转移种子的torrent文件和fastresume文件
    3、在BT/keep创建链接到savedpath
    4、调用tr增加种子
    5，修改QB标签为”转移做种“
    6、加入tr_category并写入文件
    最后，再调用一下checktorrent(tr)
    """
    global gTRCategoryUpdate
    
    try:
        tr_client = transmissionrpc.Client(TR_IP, port=TR_PORT,user=TR_USER,password=TR_PWD)
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        DebugLog("connected to QB and TR")
    except:
        DebugLog("failed to connect QB  or TR")
        return -1
    
    tNumber = 0
    for qb_torrent in qb_client.torrents_info():        
        #只对QB的”保种“类别，状态为停止的种子才进行转移
        if not(qb_torrent.state[:5].lower() == 'pause' and qb_torrent.category == '保种') : 
            continue
        #备份转移种子的torrent文件和fastresume文件
        tTorrentFile = os.path.join(QBBackupDir,qb_torrent.hash+".torrent")
        tDestTorrentFile = os.path.join(QBTorrentsBackupDir,qb_torrent.hash+".torrent")
        tResumeFile  = os.path.join(QBBackupDir,qb_torrent.hash+".fastresume")
        tDestResumeFile  = os.path.join(QBTorrentsBackupDir,qb_torrent.hash+".fastresume")
        try:
            shutil.copyfile(tTorrentFile,tDestTorrentFile)
            shutil.copyfile(tResumeFile ,tDestResumeFile)
        except:
            #print(tTorrentFile)
            #print(tResumeFile)
            #print(tDestTorrentFile)
            ErrorLog("failed to copy torrent and resume file:"+gTorrentList[i].HASH)
            #continue

        #test
        #print(str(gTorrentList[i].IsRootFolder)+'|'+gTorrentList[i].SavedPath+'|'+gTorrentList[i].RootFolder+'|'+gTorrentList[i].DirName)
        #for file in gTorrentList[i].FileName: print(file)
        tNoOfList = FindTorrent(QB,qb_torrent.hash)
        if gTorrentList[tNoOfList].IsRootFolder == True :  
            tDestSavedPath = os.path.realpath(gTorrentList[tNoOfList].SavedPath)
        else :   #为TR的保存路径创建链接
            tLink = os.path.join(TRSeedFolderList[0],gTorrentList[tNoOfList].Name) 
            try:    
                if not os.path.exists(tLink) :
                    os.symlink(os.path.realpath(gTorrentList[tNoOfList].SavedPath),tLink)
            except:
                ErrorLog("failed create link:ln -s "+os.path.realpath(gTorrentList[tNoOfList].SavedPath)+" "+tLink)
                continue            
            tDeskSavedPath = TRSeedFolderList[0]
        #TR加入种子
        try:
            tr_torrent = tr_client.add_torrent(torrent=tTorrentFile,download_dir=tDeskSavedPath,paused=True)
        except ValueError as err:
            print(err)
            ErrorLog("failed to add torrent:"+tTorrentFile)
            continue
        except  transmissionrpc.TransmissionError as err:
            print(err)
            ErrorLog("failed to add torrent:"+tTorrentFile)
            continue            
        except transmissionrpc.HTTPHandlerError as err:
            print(err)
            ErrorLog("failed to add torrent:"+tTorrentFile)
            continue               
        else:
            DebugLog("move torrent to tr:"+tr_torrent.name+'::'+tr_torrent.hashString)
        #QB设置类别为"转移"
        try:
            #qb_torrent = qb_client.get_torrent(hash=gTorrentList[i].HASH)
            qb_torrent.set_category("转移")
        except:
            ErrorLog("failed to set category:"+gTorrentList[tNoOfList].Name)
        else:
            gTorrentList[tNoOfList].Category = "转移"
            
        #加入TRCategoryList
        gTRCategoryList.append({'Category':"保种", 'HASH':tr_torrent.hashString, 'Name':tr_torrent.name})
        tNumber += 1

    if tNumber > 0 : gTRCategoryUpdate = True
    return tNumber
#end def MoveTorrents    

def SaveTorrents():
    """
    将QB中类别为'save'的种子保存到tobe目录
    0、暂停种子
    1、从rss表中获取toubanid和imdbid
    2、根据doubanid或者imdbid刮削豆瓣电影信息
    3、移入或者更名至tobe目录下的目录文件夹
    4 下载poster.jpg文件    
    5、检查该目录并加入表
    6、更新豆瓣刮削信息到表movies
    7、把种子分类设为空  
    """
    
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        DebugLog("connected to QB for saveTorrents")
    except:
        DebugLog("failed to connect QB  for saveTorrents")
    
    for torrent in qb_client.torrents_info():        
        if torrent.category != "save" : continue
        torrent.pause()
        
        #1、从rss表中获取toubanid和imdbid
        HASH = torrent.hash
        g_DB = mysql.connector.connect( host="localhost",  user="dummy",  passwd="" , database="db_movies")
        g_MyCursor = g_DB.cursor()
        sel_sql = 'select doubanid,imdbid from rss where id = %s'
        sel_val = (HASH,)
        g_MyCursor.execute(sel_sql,sel_val)
        SelectResult = g_MyCursor.fetchall()
        if len(SelectResult) != 1: ErrorLog("failed to find doubanid or imdbid :{}".format(torrent.name)); continue

        #2、根据doubanid或者imdbid刮削豆瓣电影信息
        DoubanID = SelectResult[0][0]
        IMDBID   = SelectResult[0][1]
        DebugLog("{}:{}::{}".format(DoubanID,IMDBID,HASH))
        if DoubanID != "" :   tMovieInfo = Gen({'site':'douban','sid':DoubanID}).gen(_debug=True)
        elif IMDBID != "" :   tMovieInfo = Gen({'site':'douban','sid':IMDBID  }).gen(_debug=True)
        else :  ErrorLog("empty link:"+torrent.name); continue
        if not tMovieInfo["success"]: ErrorLog("failed to request from douban:"+torrent.name); continue
 
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
        elif tNation == '中国大陆': tNation = '国'
        elif tNation == '中国台湾': tNation = '台'
        elif tNation == '日本'    : tNation = '日'
        else : pass
        tIndex = tIMDBScore.find('/')
        if tIndex > 0: tIMDBScore = tIMDBScore[:tIndex]
        else:          tIMDBScore = ""
        #判断类型，纪录片，电视剧，电影
        if tGenre.find('纪录') >= 0 :tType = 2
        elif tEpisodes > 0          :tType = 1
        else                        :tType = 0             

        #3、移入或者更名至tobe目录下的目录文件夹 
        #3.1 组装目标文件夹名需要先获取Number和Copy
        Number = Copy = 0
        if tIMDBID == "" : ErrorLog("empty IMDBID:"+torrent.name); continue
        g_DB = mysql.connector.connect( host="localhost",  user="dummy",  passwd="" , database="db_movies")
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
            DebugLog("2+ record in movies where imdbid = "+IMDBID)
            Number = SelectResult[0][0]
            for i in range(len(SelectResult)):
                if SelectResult[i][0] != Number:
                    ErrorLog("diff number in case of same imdbid:"+IMDBID)
                    break
        g_DB.close()
        
        #3.2 组装新的目标文件夹名
        tTorrentName = re.sub(u"[\u4e00-\u9f50]+","",torrent.name) #去掉name中的中文字符
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
        if os.path.exists(DestDirName):   DebugLog("DirName exists:"+DestDirName)
        else:
            if os.path.exists(tToBeDirName):  srcDirName = tToBeDirName  #从tobe目录中去改名
            else:                             srcDirName = tSaveDirName  #去原始保存目录移动到目标目录
            try:
                #原种子没有目录只是一个文件，那就新建目标目录，move函数就会把这个文件移动到目标目录
                if os.path.isfile(srcDirName): os.mkdir(DestDirName) 
                shutil.move(srcDirName,DestDirName)
            except Exception as err:
                ErrorLog("failed to mv dir:"+DestDirName)
                print(err)
                continue
            else:  DebugLog("success mv dir to tobe:"+DestDirName)

        #4 下载poster.jpg文件
        DestFullFile=os.path.join(DestDirName,"poster.jpg")
        try:
            f=requests.get(tPoster)
            with open(DestFullFile,"wb") as code:
                code.write(f.content)
        except Exception as err:
            print(err)
            ErrorLog("failed to download poster.jpg from:"+tPoster)
        else : DebugLog("success download jpg file")

        #5 检查该目录并加入表
        tMovie = movie.Movie(ToBePath, DirName)
        if tMovie.CheckMovie() != 1      :  ErrorLog("failed to check:"+DirName)  #; continue，继续插入表
        if tMovie.CheckTable("tobe") != 1:  ErrorLog("faied to table:"+DirName); continue
        else : DebugLog("success insert table")
        
        #6 更新豆瓣刮削信息到表movies
        g_DB = mysql.connector.connect( host="localhost",  user="dummy",  passwd="" , database="db_movies")
        g_MyCursor = g_DB.cursor()
        up_sql = "update movies set \
                 DoubanID=%s,IMDBID=%s,ForeignName=%s,Director=%s,Actors=%s,Episodes=%s,Poster=%s,DoubanScore=%s,IMDBScore=%s,OtherNames=%s where Number=%s and Copy=%s"
        up_val =(tDoubanID,  tIMDBID,  tForeignName,  tDirector,  tActors,  tEpisodes, tPoster,  tDoubanScore,   tIMDBScore, tOtherNames,         Number,       Copy)
        try:
            g_MyCursor.execute(up_sql,up_val)
            g_DB.commit()
        except Exception as err:
            print(err)
            ErrorLog("update error:"+DirName+":"+up_sql)
            g_DB.close()
            continue
        else:
            g_DB.close()
            DebugLog("success update table:"+DirName)
        
        #7 把种子分类设为空    
        torrent.set_category(category="")
    return 1
    
def StopQB():

    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)            
        qb_client.auth_log_in()
        qb_client.torrents.pause.all()
        qb_client.app_shutdown()
    except:
        DebugLog("failed to stop QB")
        return False
    else:
        DebugLog("success to stop QB")
        return True
        
def SartQB():

    if os.system("/usr/bin/qbittorrent &") == 0 : DebugLog ("success to start qb")
    else : debugLog("failed to start qb"); return False
    
    time.sleep(10)
    try:
        qb_client = qbittorrentapi.Client(host=QB_IPPORT, username=QB_USER, password=QB_PWD)
        qb_client.auth_log_in()
        torrents = qb_client.torrents.info()
    except:
        debugLog("failed to resume qb torrents")
        return False
        
    for torrent in torrents:
        if torrent.category == '下载' or torrent.category == '刷上传' or torrent.category == '保种' : 
            try:
                torrent.resume()
            except:
                DebugLog("failed to resume:"+torrent.name)
    return True
    
def TrackerData():

    global FRDSDataList  
    global MTeamDataList 
    global HDHomeDataList
    global BeiTaiDataList
    global JoyHDDataList 
    global SoulVoiceDataList
    global PTHomeDataList
    global PTSBaoDataList
    global LeagueHDDataList
    global HDAreaDataList
    global AVGVDataList 
    global HDSkyDataList 

    tFRDSData = 0
    tMTeamData = 0
    tHDHomeData = 0
    tBeiTaiData = 0
    tJoyHDData = 0
    tSoulVoiceData = 0
    tPTHomeData = 0
    tPTSBaoData = 0
    tLeagueHDData = 0
    tHDAreaData = 0
    tAVGVData  = 0    
    tHDSkyData  = 0    
    i = 0
    while i < len(gTorrentList):
        if len(gTorrentList[i].DateData) == 0 : ErrorLog("datedata is null:"+gTorrentList[i].HASH); i+=1; continue
        elif len(gTorrentList[i].DateData) == 1 :
            tData = gTorrentList[i].DateData[0]['Data']
        else:
            tData = gTorrentList[i].DateData[-1]['Data']-gTorrentList[i].DateData[-2]['Data']
    
        Tracker = gTorrentList[i].Tracker
        if   Tracker.find("frds") >= 0:        tFRDSData += tData
        elif Tracker.find("m-team") >= 0:      tMTeamData += tData
        elif Tracker.find("hdhome") >= 0:     tHDHomeData += tData
        elif Tracker.find("beitai") >= 0:     tBeiTaiData += tData
        elif Tracker.find("joyhd")  >= 0:     tJoyHDData += tData
        elif Tracker.find("soulvoice") >= 0:  tSoulVoiceData += tData
        elif Tracker.find("pthome") >= 0:     tPTHomeData += tData
        elif Tracker.find("ptsbao") >= 0:     tPTSBaoData += tData
        elif Tracker.find("leaguehd") >= 0:   tLeagueHDData += tData
        elif Tracker.find("hdarea") >= 0:     tHDAreaData += tData
        elif Tracker.find("avgv") >= 0:       tAVGVData += tData
        elif Tracker.find("hdsky") >= 0:      tHDSkyData += tData
        else: ErrorLog("unknown tracker:"+gTorrentList[i].HASH); i+=1; continue
        i += 1
    
    FRDSDataList.append({'Date':gToday,'Data':tFRDSData})
    MTeamDataList.append({'Date':gToday,'Data':tMTeamData})
    HDHomeDataList.append({'Date':gToday,'Data':tHDHomeData})
    BeiTaiDataList.append({'Date':gToday,'Data':tBeiTaiData})
    JoyHDDataList.append({'Date':gToday,'Data':tJoyHDData})
    SoulVoiceDataList.append({'Date':gToday,'Data':tSoulVoiceData})
    PTHomeDataList.append({'Date':gToday,'Data':tPTHomeData})
    PTSBaoDataList.append({'Date':gToday,'Data':tPTSBaoData})
    LeagueHDDataList.append({'Date':gToday,'Data':tLeagueHDData})
    HDAreaDataList.append({'Date':gToday,'Data':tHDAreaData})
    AVGVDataList.append({'Date':gToday,'Data':tAVGVData})
    HDSkyDataList.append({'Date':gToday,'Data':tHDSkyData})


    if len(FRDSDataList) > 30: del FRDSDataList[0]
    if len(MTeamDataList) > 30: del MTeamDataList[0]
    if len(HDHomeDataList) > 30: del HDHomeDataList[0]
    if len(BeiTaiDataList) > 30: del BeiTaiDataList[0]
    if len(JoyHDDataList) > 30: del JoyHDDataList[0]
    if len(SoulVoiceDataList) > 30: del SoulVoiceDataList[0]
    if len(PTHomeDataList) > 30: del PTHomeDataList[0]
    if len(PTSBaoDataList) > 30: del PTSBaoDataList[0]
    if len(LeagueHDDataList) > 30: del LeagueHDDataList[0]
    if len(HDAreaDataList) > 30: del HDAreaDataList[0]
    if len(AVGVDataList) > 30: del AVGVDataList[0]
    if len(HDSkyDataList) > 30: del HDSkyDataList[0]

    DebugLog("FRDS      upload(M):"+str(tFRDSData/(1000*1000)))
    DebugLog("MTeam     upload(M):"+str(tMTeamData/(1000*1000)))
    DebugLog("HDHome    upload(M):"+str(tHDHomeData/(1000*1000)))
    DebugLog("BeiTai    upload(M):"+str(tBeiTaiData/(1000*1000)))
    DebugLog("JoyHD     upload(M):"+str(tJoyHDData/(1000*1000)))
    DebugLog("SoulVoice upload(M):"+str(tSoulVoiceData/(1000*1000)))
    DebugLog("PTHome    upload(M):"+str(tPTHomeData/(1000*1000)))
    DebugLog("PTSBao    upload(M):"+str(tPTSBaoData/(1000*1000)))
    DebugLog("LeagueHD  upload(M):"+str(tLeagueHDData/(1000*1000)))
    DebugLog("HDArea    upload(M):"+str(tHDAreaData/(1000*1000)))
    DebugLog("AVGV      upload(M):"+str(tAVGVData/(1000*1000)))
    DebugLog("HDSky     upload(M):"+str(tHDSkyData/(1000*1000)))

    DebugLog("FRDS      "+GetDaysOfNoUpload(FRDSDataList)+" days no upload")
    DebugLog("MTeam     "+GetDaysOfNoUpload(MTeamDataList)+" days no upload")
    DebugLog("HDHome    "+GetDaysOfNoUpload(HDHomeDataList)+" days no upload")
    DebugLog("BeiTai    "+GetDaysOfNoUpload(BeiTaiDataList)+" days no upload")
    DebugLog("JoyHD     "+GetDaysOfNoUpload(JoyHDDataList)+" days no upload")
    DebugLog("SoulVoice "+GetDaysOfNoUpload(SoulVoiceDataList)+" days no upload")
    DebugLog("PTHome    "+GetDaysOfNoUpload(PTHomeDataList)+" days no upload")
    DebugLog("PTSBao    "+GetDaysOfNoUpload(PTSBaoDataList)+" days no upload")
    DebugLog("LeagueHD  "+GetDaysOfNoUpload(LeagueHDDataList)+" days no upload")
    DebugLog("HDArea    "+GetDaysOfNoUpload(HDAreaDataList)+" days no upload")
    DebugLog("AVGV      "+GetDaysOfNoUpload(AVGVDataList)+" days no upload")
    DebugLog("HDSKy     "+GetDaysOfNoUpload(HDSkyDataList)+" days no upload")
    
    return 1
    
def ReadTrackerBackup():
    """
    读取TrackerList的备份文件，用于各个Tracker的上传数据
    """
    global FRDSDataList  
    global MTeamDataList 
    global HDHomeDataList
    global BeiTaiDataList
    global JoyHDDataList 
    global SoulVoiceDataList
    global PTHomeDataList
    global PTSBaoDataList
    global LeagueHDDataList
    global HDAreaDataList
    global AVGVDataList 
    global HDSkyDataList 
    
    #
    if not os.path.isfile(TrackerListBackup):
        DebugLog(TrackerListBackup+" does not exist")
        return 0
        
    for line in open(TrackerListBackup):
        Tracker,tDateDataStr = line.split('|',1)
        if tDateDataStr [-1:] == '\n' :  tDateDataStr = tDateDataStr[:-1]  #remove '\n'
        tDateDataList = tDateDataStr.split(',')

        i = 0 ; DateData = []
        while i < len(tDateDataList) :
            if tDateDataList[i] == "" :  break      #最后一个可能为空就退出循环
            tDate = (tDateDataList[i])[:10]
            tData = int( (tDateDataList[i])[11:] )
            DateData.append({'Date':tDate,'Data':tData})
            i += 1

        if   Tracker == "FRDS":  FRDSDataList = DateData           
        elif Tracker == "MTeam": MTeamDataList = DateData
        elif Tracker == "HDHome": HDHomeDataList = DateData
        elif Tracker == "BeiTai": BeiTaiDataList = DateData
        elif Tracker == "JoyHD":     JoyHDDataList = DateData
        elif Tracker == "SoulVoice": SoulVoiceDataList = DateData
        elif Tracker == "PTHome": PTHomeDataList = DateData
        elif Tracker == "PTSBao": PTSBaoDataList = DateData
        elif Tracker == "LeagueHD": LeagueHDDataList = DateData
        elif Tracker == "HDArea": HDAreaDataList = DateData
        elif Tracker == "AVGV": AVGVDataList = DateData
        elif Tracker == "HDSky": HDSkyDataList = DateData
        else :  ErrorLog("unknown track in TrackBackup:"+Tracker) 
        
    #end for 
    return 1

def GetDateDataStr(tTrackerList):

    j = 0 ; tDateDataListStr = ""
    while j < len(tTrackerList):        
        tDateDataStr = tTrackerList[j]['Date']+":" + str(tTrackerList[j]['Data'])
        tDateDataListStr += tDateDataStr+','
        j += 1
    if tDateDataListStr[-1:] == ',' : tDateDataListStr = tDateDataListStr[:-1] #去掉最后一个','
        
    return tDateDataListStr  

def GetDaysOfNoUpload(tTrackerList):
    i=len(tTrackerList)-1
    NumberOfDays=0
    while i >= 0 :
        if tTrackerList[i]['Data'] == 0:
            NumberOfDays += 1
        else:
            break
        i -= 1
    return str(NumberOfDays).zfill(2)

def WriteTrackerBackup():
    """
 
    """

    if gIsNewDay == True :
        tThisMonth = gToday[0:7] ; tThisYear = gToday[0:4]
        if tThisMonth[5:7] == "01" : 
            tLastMonth = str(int(tThisYear)-1)+"-"+"12"      
        else : 
            tLastMonth = tThisYear+"-"+str(int(tThisMonth[5:7])-1).zfill(2)
        
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
    else :
        LogClear(TrackerListBackup)        

    try :
        fo = open(TrackerListBackup,"w")
    except:
        ErrorLog("Error:open ptbackup file to write："+TrackerListBackup)
        return -1
             
    tStr = "FRDS|"     +GetDateDataStr(FRDSDataList);  fo.write(tStr+'\n')
    tStr = "MTeam|"    +GetDateDataStr(MTeamDataList);  fo.write(tStr+'\n')
    tStr = "HDHome|"   +GetDateDataStr(HDHomeDataList);  fo.write(tStr+'\n')
    tStr = "BeiTai|"   +GetDateDataStr(BeiTaiDataList);  fo.write(tStr+'\n')
    tStr = "JoyHD|"    +GetDateDataStr(JoyHDDataList);  fo.write(tStr+'\n')
    tStr = "SoulVoice|"+GetDateDataStr(SoulVoiceDataList);  fo.write(tStr+'\n')
    tStr = "PTHome|"   +GetDateDataStr(PTHomeDataList);  fo.write(tStr+'\n')
    tStr = "PTSBao|"   +GetDateDataStr(PTSBaoDataList);  fo.write(tStr+'\n')
    tStr = "LeagueHD|" +GetDateDataStr(LeagueHDDataList);  fo.write(tStr+'\n')
    tStr = "HDArea|"   +GetDateDataStr(HDAreaDataList);  fo.write(tStr+'\n')
    tStr = "AVGV|"     +GetDateDataStr(AVGVDataList);  fo.write(tStr+'\n')
    tStr = "HDSky|"    +GetDateDataStr(HDSkyDataList);  fo.write(tStr+'\n')
    
    fo.close()
    DebugLog("success write tracklist")
    
    return 1
#end def WritePTBackup
  
if __name__ == '__main__' :

    tCurrentTime = datetime.datetime.now()
    
    DebugLog("Begin ReadPTBackup from "+TorrentListBackup)
    if ReadPTBackup() == 1:
        DebugLog("success ReadPTBackup. set gLastCheckDate="+gLastCheckDate)
        DebugLog(str(len(gTorrentList)).zfill(4)+" torrents readed.")
    if ReadTRCategory() == 1:
        DebugLog("success ReadTRCategory:"+str(len(gTRCategoryList)).zfill(4)+" torrents readed.")
    if ReadIgnoreList() == 1:
        DebugLog("success ReadIgnoreList:")
        for tFile in gPTIgnoreList : DebugLog(tFile['Path']+"::"+tFile['Name'])      

    if ReadTrackerBackup() == 1:  DebugLog("success ReadTrackerBackup:"+TrackerListBackup)
    
    if len(sys.argv) >= 2 :
        #如果输入参数为now时，执行一次性的检查任务
        if sys.argv[1] == "now":
            gIsNewDay = True; NUMBEROFDAYS += 1
            DebugLog("check torrents immediately one time","p")
            CheckTorrents(TR)
            CheckTorrents(QB)
            DebugLog("begin MoveTorrents","p")
            tNumber = MoveTorrents()
            DebugLog(str(tNumber)+" torrents moved")
        #执行输入参数为checkdisk执行的命令    
        elif sys.argv[1] == "checkdisk":
            DebugLog("begin check disk one time","p")
            if CheckTorrents(TR) != -1 and CheckTorrents(QB) != -1:
                for DiskPath in CheckDiskList:  CheckDisk(DiskPath)
            DebugLog("end check disk","p")
        else: pass
        exit()
        
    while 1 == 1:
        gTRCategoryUpdate = False
        tCurrentTime = datetime.datetime.now()
        gToday = tCurrentTime.strftime('%Y-%m-%d')
        if gToday != gLastCheckDate :      gIsNewDay = True
        else:                              gIsNewDay = False
        
        tTRReturn = CheckTorrents(TR)
        tQBReturn = CheckTorrents(QB)
        if tTRReturn == 1 or tQBReturn == 1:  #有变化,重新写一次备份文件
            DebugLog("begin WritePTBackup to"+TorrentListBackup)
            if WritePTBackup() == 1:
                DebugLog(str(len(gTorrentList)).zfill(4)+" torrents writed.")  
                
        if gIsNewDay :  
            TrackerData()
            WriteTrackerBackup()

        #转移QB的种子（停止状态，分类为保种）到TR做种
        tNumber = MoveTorrents()
        if tNumber > 0 : DebugLog(str(tNumber)+" torrents moved")
        
        #写入TRCategory
        if gTRCategoryUpdate == True : WriteTRCategory()
        
        #将QB分类为save的种子保存到tobe目录
        SaveTorrents()
        
        #检查一下内存占用
        tMem = psutil.virtual_memory()
        DebugLog("memory percent used:"+str(tMem.percent))
        if tMem.percent >= 95: 
            if StopQB() == True :
                time.sleep(600)
                SartQB()
                
        gLastCheckDate = tCurrentTime.strftime("%Y-%m-%d")
        DebugLog("update gLastCheckDate="+gLastCheckDate)        
        DebugLog("begin sleep")
        time.sleep(1800)   #睡眠半小时
        
    

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
import qbittorrent 
import transmissionrpc
 
"""
一、读取备份种子数据，建立种子列表
备份文件在TorrentListBackup
二、每隔半个小时执行任务：访问QB和TR(QB/TR的用户密码等写在程序），获取种子列表，逐个进行分析
1、对于下载保存路径不在RootFolderList中的种子，报错，暂停
2、检查文件是否存在（半小时仅检查第一个文件，隔天完整检查一次），文件不存在就报错，暂停
3、新的一天，记录当天的种子上传量（绝对值），开始统计NUMBEROFDAYS内的相对下载量，
    如果连续NUMBEROFDAYS内上传量低于阈值UPLOADTHRESHOLD，就认为最近低上传。而且不属于保种的种子就暂停。如何判断是否属于保种呢？
    对于QB：如果种子分类不属于'保种'的，就暂停种子。
    对于TR：如果报错路径不是"TRSEEDINGPATH"，就暂停种子
4、为了方便QB的WEB页浏览，我根据TRACKER进行了标签设置，这样如果可以自动设置标签（我目前区分为frds/mteam/other）
5、最后更新列表并写入备份文件

修订记录：
-、2020-03-15 12:00：V2.0：
    1、重新用transmissionrpc，python-qbittorrent接口编写。
    2、封装了两个客户端的不同，简化代码
    3、重新整理了日志
    不足：1、不支持QB的tags设定
二、2020-03-16:V2.1，
    1,判断IsLowUpload后，需要判断种子状态，对于已经为停止/暂停状态的种子不做处理。
    2,修订原来TRSEEDPATH仅为单一目录，更改为目录列表：TRSeedFolerList，
    3、增加一个立即执行的入口，pt.py now就会立即执行一次检查，仅检查种子并处理，但不写入backup文件
三、2020-03-17：V2.2
    1,GetDirName, files == 1, bug
    2,checkdisk
"""

 
#程序运行设置
NUMBEROFDAYS = 3                           #连续多少天低于阈值
UPLOADTHRESHOLD = 10000000                 #阈值，单位Bytes
TorrentListBackup = "/root/.local/share/data/pt/pt.txt"  #种子信息备份目录（重要的是每天的上传量）
DebugLogFile = "log/debug.log"             #日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/error.log"             #错误日志
                                           #TR的保种路径，如果多个就需要修改代码
TRSeedFolderList = ["/media/root/BT/keep" ,"/root/e52/books"]
                                           #下载保存路径的列表，不在这个列表中的种子会报错
RootFolderList = [  "/sg3t",\
                    "/media/root/wd4t",\
                    "/media/root/BT/keep",\
                    "/media/root/BT/temp",\
                    "/media/root/BT/music",\
                    "/media/root/BT/movies",\
                    "/root/e52/books" ]
PathLength = len("/media/root/BT/movies")
CheckDiskList = [ "/media/root/wd4t","/media/root/BT/movies"]
IgnoreListFile = "config/ignore.txt"
                        

#程序易读性用，请勿修改
SEEDING  = 0
DOWNLOAD = 1
UPLOAD   = 2
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
global LastCheckDate 
global gIsNewDay
global gToday
gPTIgnoreList = []
gTorrentList = []
gLastCheckDate = "1970-01-01"
gIsNewDay = 0
gToday = "1970-01-01"

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

#一些和运行环境无关的自定义函数############################################################### 
def GetPhysicalPath(Path):
    """
    目的：将可能含链接的路径Path，转换为物理路径，然后返回
    
    输入：Path必须为绝对路径(以/开始),而且必须存在
    返回值：物理路径，出错就否则为""
    """
    #首先检查Path的合法性：
    tPathStr = Path.strip()
    if tPathStr[:1] != '/'  : return ""   #第一个字符必须为/，表示是绝对路径
    if not(os.path.isdir(tPathStr)) : return ""
    
    #DebugLog("before GetPhy:"+Path)
    tPathStr = Path.strip()
    if tPathStr[-1:] == '/' : tPathStr = tPathStr[:-1]    #去掉最后的'/'
        
    tPathStr = Path[1:]  #去掉第一个/
    tDestPath = "/"
    tFindIndex = 0
    while tPathStr.find('/') != -1 :
        tFindIndex = tPathStr.find('/')
        tPath1 = os.path.join(tDestPath,tPathStr[:tFindIndex])
        if os.path.islink(tPath1) :
            tPath2 = os.readlink(tPath1)
            if tPath2[:1] != '/' : #说明返回的不是绝对路径,那就把它join到tDestPath
                tDestPath = os.path.join(tDestPath,tPath2)
            else:
                tDestPath = tPath2
            #tDestPath = GetPhysicalPath(tDestPath) #再递归一下，确认tDestPath不再有链接
            tPathStr = tPathStr[tFindIndex+1:]
        else :
            tDestPath = os.path.join(tDestPath,tPathStr[:tFindIndex])
            tPathStr = tPathStr[tFindIndex+1:]
        #DebugLog("tDestPath="+tDestPath+"  "+"tPathStr="+tPathStr)
    #while结束后，最后一层目录
    tPath1 = os.path.join(tDestPath,tPathStr)
    if os.path.islink(tPath1) :
        tPath2 = os.readlink(tPath1)
        if tPath2[:1] != '/' : #说明返回的不是绝对路径,那就把它join到tDestPath
            tDestPath = os.path.join(tDestPath,tPath2)
        else:
            tDestPath = tPath2
        #tDestPath = GetPhysicalPath(tDestPath) #再递归一下，确认tDestPath不再有链接
    else :
        tDestPath = os.path.join(tDestPath,tPathStr)
    
    #DebugLog("after GetPhy:"+tDestPath)
    return tDestPath
#end def GetPhysicalPath

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
        if SrcDir[:tLenDest] == tDestDir :  return 1
        i += 1
    return 0
########################################################################################

class TorrentInfo :
    def __init__(self,Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData):
        
        self.Client = Client          #"TR" "QB" 
        self.HASH = HASH              #HASH
        #self.ID
        self.Name = Name 
        self.Done = Done              #完成率*100,取整后转换为数字
        self.Status = Status          #for TR:4位字符，Idle,Stop,Down,UP &,Seed
                                      #for QB:4位字符，取自：PausedUP，PausedDL，downloading，stalledUP
        self.Category = Category      #分类：0:做种 1:下载 2:刷上传
        self.Tags  = Tags             #标签
        self.SavedPath = SavedPath    #保存路径/media/root/BT/movies(temp),wd4t等

        self.AddDateTime = AddDateTime#种子加入时间
        self.DateData = DateData      #用于记录最近5天的上传数据，是一个数组,数组里面是字典
                                      #例如:['Date':2020-03-10,'Data':100,'Date':2020-03-11,'Data':200]
                                      #Data:，int类型，新的一天第一次数据，绝对数。单位M
                                      #正常运行时应该是每一天一条数据，而且是日期是连续的。但如果程序退出并保存数据后，很长时间再重新启动，就会出现日期不连续
                                      #这个时候会有误差，忽略不计吧                                  

        self.FileName = []            #存储文件的数组
                                      #名字,大小，完成率
        self.DirName = ""             #种子目录名称
        self.RootFolder = ""          #种子保存的路径所在根目录

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
            Name = files[i]['name']  
            Size = files[i]['size']
            #Done = int (files[i]['completed']/Size * 100)    
            self.FileName.append( {'Name':Name,'Size':Size} )
            i += 1
        
        """#对于QB检查并设置标签，frds,mteam,other
        if self.Client == QB:
            Tracker = torrent['tracker']
            Tags = torrent['tags']
            if Tracker.find("keepfrds") >= 0 :
                if Tags != 'frds':
                    torrent.remove_tags()
                    torrent.add_tags('frds')
            elif Tracker.find("m-team") >= 0 :
                if Tags != 'mteam':
                    torrent.remove_tags()
                    torrent.add_tags('mteam')
            else:
                if Tags != 'other':
                    torrent.remove_tags()
                    torrent.add_tags('other')
        """
        
        #检查文件是否存在，一天完整检查一次，否则仅检查第一个文件
        if self.Done == 100 :
            if gIsNewDay == 1 :
                i = 0 
                while i < len(self.FileName) :
                    tFullFileName = os.path.join(self.SavedPath, self.FileName[i]['Name'])
                    if not os.path.isfile(tFullFileName):
                        ErrorLog(tFullFileName+" does not exist")
                        return CHECKERROR
                    if self.FileName[i]['Size'] != os.path.getsize(tFullFileName) :
                        ErrorLog(tFullFileName+" file size error. torrent size:"+str(self.FileName[i]['Size']))
                        return CHECKERROR
                    i+=1
            else :
                tFullFileName = os.path.join(self.SavedPath, self.FileName[0]['Name'])
                if not os.path.isfile(tFullFileName) :
                    ErrorLog(tFullFileName+" does not exist")
                    return CHECKERROR
        
        #获取RootFolder和DirName
        if self.GetDirName() == -1:
            return CHECKERROR
        
        #更新TorrentList        
        #首先找该种子是否存在
        tNoOfTheList = FindTorrent(self.HASH)
        if tNoOfTheList == -1 : #没找到，说明是新种子，加入TorrentList
            gTorrentList.append(self)
            DebugLog("add torrent, name="+self.Name)
            return ADDED
        
        #找到旧种子，进行检查和更新操作
        tUpdate = 0
        if gTorrentList[tNoOfTheList].Name        != self.Name       : gTorrentList[tNoOfTheList].Name        = self.Name       ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Done        != self.Done       : gTorrentList[tNoOfTheList].Done        = self.Done       ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Status      != self.Status     : gTorrentList[tNoOfTheList].Status      = self.Status     ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Category    != self.Category   : gTorrentList[tNoOfTheList].Category    = self.Category   ; tUpdate += 1
        if gTorrentList[tNoOfTheList].Tags        != self.Tags       : gTorrentList[tNoOfTheList].Tags        = self.Tags       ; tUpdate += 1
        if gTorrentList[tNoOfTheList].SavedPath   != self.SavedPath  : gTorrentList[tNoOfTheList].SavedPath   = self.SavedPath  ; tUpdate += 1
        if gTorrentList[tNoOfTheList].AddDateTime != self.AddDateTime: gTorrentList[tNoOfTheList].AddDateTime = self.AddDateTime; tUpdate += 1
        if gTorrentList[tNoOfTheList].RootFolder  != self.RootFolder : gTorrentList[tNoOfTheList].RootFolder  = self.RootFolder ; tUpdate += 1
        if gTorrentList[tNoOfTheList].DirName     != self.DirName    : gTorrentList[tNoOfTheList].DirName     = self.DirName    ; tUpdate += 1
        if gTorrentList[tNoOfTheList].FileName    != self.FileName   : gTorrentList[tNoOfTheList].FileName    = self.FileName   ; tUpdate += 1

        gTorrentList[tNoOfTheList].Checked = 1         
        
        if gIsNewDay == 1 :   #新的一天，更新记录每天的上传量（绝对值）
            gTorrentList[tNoOfTheList].DateData.append(self.DateData[0])
            if len(gTorrentList[tNoOfTheList].DateData) >= NUMBEROFDAYS+3: del gTorrentList[tNoOfTheList].DateData[0] #删除前面旧的数据
            
            if IsLowUpload(gTorrentList[tNoOfTheList].DateData) == 1 :
                if self.Status[:4].lower() != 'stop' and self.Status[:4].lower() != 'paus' :
                    if gTorrentList[tNoOfTheList].Client == QB and gTorrentList[tNoOfTheList].Category != '保种' : return LOWUPLOAD 
                    elif gTorrentList[tNoOfTheList].Client == TR  and IsSubDir(gTorrentList[tNoOfTheList].SavedPath,TRSeedFolderList) == 0 :  return LOWUPLOAD
                    else :   return UPDATED
     
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
        Status = torrent.status
        Category = ""
        Tags = ""
        SavedPath = torrent.downloadDir
        AddDateTime = time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime(torrent.addedDate) ) 
        DateData = [] ;  DateData.append({'Date':gToday,'Data':torrent.uploadedEver})  
    else :
        HASH = torrent['hash']
        Name = torrent['name']
        Done = int(torrent['progress']*100)
        Status = torrent['state']
        Category = torrent['category']
        Tags = torrent['tags']
        SavedPath = torrent['save_path']
        AddDateTime = time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime(torrent['added_on']) ) 
        DateData = [] ;  DateData.append({'Date':gToday,'Data':torrent['uploaded']})   

    return  TorrentInfo(Client,HASH,Name,Done,Status,Category,Tags,SavedPath,AddDateTime,DateData)
    
def IsLowUpload(DateData):
    """
    检查DateData中的数据，如果连续三天上传增量数据低于阈值就返回1，否则返回0
    """
    #包括今天在内，至少要有NUMBEROFDAYS+1天数据
    tLength = len(DateData)
    if tLength < NUMBEROFDAYS + 1:     return 0

    #从尾部开始循环，尾部日期是最新的
    i = tLength - 1; tDays = 0  
    while i > 1 and tDays < NUMBEROFDAYS:
        tDeltaData = (DateData[i])['Data'] - (DateData[i-1])['Data']
        if tDeltaData < UPLOADTHRESHOLD :    tDays += 1
        else:    return 0  #有一天高于阈值就退出
        i -= 1
    
    #运行到这，tDays应该就等于NUMBEROFDAYS,不过代码还是加一个判断
    if tDays >= NUMBEROFDAYS : return 1
    else : return 0
        
def FindTorrent(HASH):
    """
    根据HASH寻找TorrentList，如果找到就返回序号，否则返回-1
    """
    global gTorrentList

    i = 0
    while i < len(gTorrentList) :
        if HASH == gTorrentList[i].HASH :  return i
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
    """

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
            tr_client = transmissionrpc.Client('localhost', port=9091,user='dummy',password='moonbeam')
            torrents = tr_client.get_torrents()
        else :
            qb_client = qbittorrent.Client('http://127.0.0.1:8989/')
            qb_client.login('admin', 'moonbeam')
            torrents = qb_client.torrents()
        DebugLog("connect to  "+Client)
    except:
        ErrorLog("failed to connect to "+Client)
        return -1
        
    # 开始逐个获取torrent并检查
    for torrent in torrents: 
        tTorrentInfo = TransformTorrent(Client,torrent)
        if Client == TR:  tReturn = tTorrentInfo.CheckTorrent(torrent.files())
        else :            tReturn = tTorrentInfo.CheckTorrent(qb_client.get_torrent_files(torrent['hash']))
        
        if tReturn == CHECKERROR :        tNumberOfError += 1
        elif tReturn == LOWUPLOAD :       tNumberOfPaused += 1
        elif tReturn == ADDED :           tNumberOfAdded += 1
        elif tReturn == UPDATED :         tNumberOfUpdated += 1
        elif tReturn == NOCHANGE:         tNumberOfNoChange += 1
        else: ErrorLog("unknown return in CheckTorrent:"+str(tReturn))

        if tReturn == CHECKERROR :  
            if Client == TR:  
                torrent.stop()
                DebugLog("stop torrent for error, name="+torrent.name)
            else :            
                qb_client.pause(torrent['hash'])
                DebugLog("stop torrent for error, name="+torrent['name'])
        if tReturn == LOWUPLOAD : 
            if Client == TR:  
                torrent.stop()
                DebugLog("stop torrent for low upload, name="+torrent.name)
            else :            
                qb_client.pause(torrent['hash'])
                DebugLog("stop torrent for low upload, name="+torrent['name'])
                
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
    DebugLog(str(tNumberOfAdded).zfill(4)+" torrents added")
    DebugLog(str(tNumberOfDeleted).zfill(4)+" torrents deleted")
    DebugLog(str(tNumberOfUpdated).zfill(4)+" torrents updated")
    DebugLog(str(tNumberOfError).zfill(4)+" torrents paused for error")
    DebugLog(str(tNumberOfPaused).zfill(4)+" torrents paused for low upload")
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
        print("find file:"+IgnoreListFile)
        for line in open(IgnoreListFile):
            Path = line[:PathLength].strip()
            Name = line[PathLength+1:].strip()
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
            return 1
        i += 1
    return 0

def InTorrentList(SavedPath,DirName):
    """
    判断SavedPath+DirName在不在TorrentList
    """
    i = 0 
    while i < len(gTorrentList) :
        tSrcDirName = os.path.join(SavedPath,DirName)
        tDestDirName = os.path.join(gTorrentList[i].RootFolder,gTorrentList[i].DirName)
        if GetPhysicalPath(tSrcDirName) == GetPhysicalPath(tDestDirName): return 1
        i += 1
    return 0
#end def InTorrentList
    
def CheckDisk(DiskPath):
    """
    对Path下的目录及文件逐个对比TorrentList，并进行标记。
    """

    DebugLog("begin check:"+DiskPath)
    for file in os.listdir(DiskPath):        
        fullpathfile = os.path.join(DiskPath,file)
        DebugLog("check:"+fullpathfile)
        if os.path.isdir(fullpathfile) or os.path.isfile(fullpathfile):        
            #一些特殊文件夹忽略
            if file == 'lost+found' or file[0:6] == '.Trash' :
                DebugLog ("ignore some dir:"+file)
                continue 
            
            if InPTIgnoreList(DiskPath,file) == 1:
                DebugLog ("in Ignore List:"+DiskPath+"::"+file)
                continue

            if InTorrentList(DiskPath,file) == 1: DebugLog(file+"::find in torrent list:")
            else :                                ErrorLog(file+"::not find in torrent list:")
        else :
            DebugLog("Error：not file or dir")
#end def CheckDisk

        
if __name__ == '__main__' :

    tCurrentTime = datetime.datetime.now()
    #LogClear(DebugLogFile)
    #LogClear(ErrorLogFile)
    
    DebugLog("Begin ReadPTBackup from "+TorrentListBackup)
    if ReadPTBackup() == 1:
        DebugLog("success ReadPTBackup. set gLastCheckDate="+gLastCheckDate)
        DebugLog(str(len(gTorrentList)).zfill(4)+" torrents readed.")
    
    if len(sys.argv) >= 2 :
        if sys.argv[1] == "now":
            gIsNewDay =1
            NUMBEROFDAYS += 1
            DebugLog("check torrents immediately one time","p")
            CheckTorrents(TR)
            CheckTorrents(QB)
            DebugLog("end check torrents one time","p")
            exit()
            
        if sys.argv[1] == "checkdisk":
            DebugLog("begin check disk","p")
            DebugLog("read ignorelist from file"+IgnoreListFile,"p")
            ReadIgnoreList()
            for tFile in gPTIgnoreList :
                DebugLog(tFile['Path']+"::"+tFile['Name'])
            for DiskPath in CheckDiskList:    CheckDisk(DiskPath)
            DebugLog("end check disk")
            exit()

    while 1 == 1:
        tCurrentTime = datetime.datetime.now()
        gToday = tCurrentTime.strftime('%Y-%m-%d')
        if gToday != gLastCheckDate :      gIsNewDay = 1
        else:                              gIsNewDay = 0
        
        tTRReturn = CheckTorrents(TR)
        tQBReturn = CheckTorrents(QB)
        
        if tTRReturn == 1 or tQBReturn == 1:  #有变化,重新写一次备份文件
            DebugLog("begin WritePTBackup to"+TorrentListBackup)
            if WritePTBackup() == 1:
                DebugLog(str(len(gTorrentList)).zfill(4)+" torrents writed.")  

        gLastCheckDate = tCurrentTime.strftime("%Y-%m-%d")
        DebugLog("update gLastCheckDate="+gLastCheckDate)        
        DebugLog("begin sleep")
        time.sleep(1800)   #睡眠半小时
        
    

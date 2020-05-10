#!/usr/bin/python3
"""
1、根据选择的目标磁盘，逐个读取硬盘目录，创建tmm映射目录和链接(忽略SP开头的视频文件)
如果已经创建目录和链接会忽略。
2、完成1后，会提示是否继续检查，y继续：
1) 检查相应磁盘对应的映射目录和链接(删除不再需要的目录和链接)
2) 比对nfo文件中的信息，包括year，name，min等，如果不一致报错。
    year会忽略1年之内的误差
    name会比较两者之间的相等或者包含关系
    min会忽略5以内的误差
3) 读取nfo中的imdbID,genre，更新至数据库
    genre会根据词典翻译成中文，多个genre会以","连接。例如动画，冒险

"""

import os
import sys
import shutil
from pathlib import Path
import time
import datetime
import re
import movie
import mysql.connector

LinkDir="/root/e52/movies/"
ToBeExecDirName = False               # DirName名称
ToBeExecRmdir   = False               # 从子文件夹将内容提上来 删除空子目录
DebugLogFile = "log/link.log"         #日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/linkerror.log"    #错误日志
ExecLogFile  = "log/link.log"
CHECKERROR = -1
CHECKNORMAL = 0
ERROR       = -1        # 错误
UPDATE      = 1         # 更新
NOCHANGE    = 0         # 无变化 
g_MyMovies = []
g_Count = 0
g_CheckDiskPath = ""
g_CheckDisk = ""
gCheckTime = ""

gDictList = (\
        ("Crime","犯罪"),\
        ("Drama","剧情"),\
        ("History","历史"),\
        ("Adventure","冒险"),\
        ("Horror","恐怖"),\
        ("Thriller","惊悚"),\
        ("Romance","浪漫"),\
        ("Comedy","喜剧"),\
        ("Music","音乐"),\
        ("Action","动作"),\
        ("Family","家庭"),\
        ("Fantasy","奇幻"),\
        ("Mystery","神秘"),\
        ("Animation","动画"),\
        ("War","战争"),\
        ("Science Fiction","科幻"),\
        ("Documentary","纪录片"),\
        ("TV Movie","电视电影"),\
        ("Western","西部"))

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

def ReadTagCont(line):
    #  <title>V for Vendetta</title>
    if line[-1:] == '\n' : line = line[:-1]
    Tag = ""
    Cont = ""
    TagCont = {'Tag':Tag,'Cont':Cont}
    if line[2:3] != '<' : return TagCont
    tIndex = line.find('>')
    if tIndex < 0 : return TagCont
    Tag = line[3:tIndex]
    
    line = line[tIndex+1:]
    tIndex = line.find('<')
    if tIndex < 0 : return TagCont
    Cont = line[:tIndex]
    TagEndStr = '</'+Tag+'>'
    if line[tIndex:] != TagEndStr : return TagCont
    return {'Tag':Tag,'Cont':Cont}
    
def Translate(word,tag=0):
    """
    中英文翻译对照
    输入：
        word :待翻译的词
        tag  :翻译标志，缺省0：英文翻译成中文，1：中文翻译成英文
    返回：成功翻译的单词，或者空""
    """
    for tDict in gDictList:
        if tag == 0:
            if tDict[0] == word: return tDict[1]
        else:
            if tDict[1] == word: return tDict[0]
    ErrorLog("unknown word:"+word)
    return word

class TMMInfo:
    def __init__(self,Number,Copy,FileName):
        self.Number = Number
        self.Copy   = Copy
        self.FileName = FileName
        self.Year = 0
        self.Name = ""
        self.EnglishName = ""
        self.imdbID = ""
        self.Min = 0
        self.GenreList = []
        self.Genre = ""
        self.IsError = False
        
    def ReadMovieNfo(self):
        
        if not os.path.isfile(self.FileName) : return -1        
        for line in open(self.FileName):            
            TagCont = ReadTagCont(line)
            Tag = TagCont['Tag']
            Cont = TagCont['Cont']
            if   Tag == 'title'         :  self.Name        = Cont
            elif Tag == 'originaltitle' :  self.EnglishName = Cont
            elif Tag == 'year'          :  self.Year        = int(Cont)
            elif Tag == 'id'            :  self.imdbID      = Cont
            elif Tag == 'runtime'       :  self.Min         = int(Cont)
            elif Tag == 'genre'         :  self.GenreList.append(Translate(Cont))
            else: pass
        
        #把Name空格替换-
        self.Name = self.Name.replace(' ','-')
        #把EnglishName空格替换.
        self.EnglishName = self.EnglishName.replace(' ','.')
        #组装一下Genre
        for tGenre in self.GenreList:
            self.Genre += tGenre+','
        if self.Genre[-1:] == ',' : self.Genre = self.Genre[:-1]
        

        
    def UpdateTable(self)   :
        """
        对tMovie信息，进行表数据更新
        更新信息：
        1、imdbID
        2、genre
        返回值：
            ERROR    错误
            UPDATE   更新
            NOCHANGE 无变化 
        """
      
        Number = self.Number
        Copy   = self.Copy
        if Number < 0 or Copy < 0 : ErrorLog("Number error:"+str(Number)+"::"+str(Copy)); return ERROR
        
        #select from movies where Number == tMovie.Number and Copy == tMovie.Copy
        se_sql = "select \
            Name,EnglishName,Year,Min,imdbID,Genre\
            from movies where Number=%s and Copy=%s"
        se_val = (Number,Copy)    
        g_MyCursor.execute(se_sql,se_val)
        tSelectResult = g_MyCursor.fetchall()
        #假如不存在就报错
        if len(tSelectResult) == 0: 
            ErrorLog("failed to find record in table:"+str(Number)+"::"+str(Copy))
            return ERROR
        #已经存在就update
        elif len(tSelectResult) == 1:
            tUpdated = 0; tSelect = tSelectResult[0]
            Name        = tSelect[0]
            EnglishName = tSelect[1]
            Year        = tSelect[2]
            Min         = tSelect[3]
            imdbID      = tSelect[4]
            Genre       = tSelect[5]
            if self.Name.find(Name) < 0 and Name.find(self.Name) < 0 : 
                ErrorLog("Name     not equal intable and tmm:"+ Name+"::"+self.Name+"::"+str(Number))
            #if Name        != self.Name       : ErrorLog("Name        not equal in table and tmm:"+Name       +"::"+self.Name+"::"+str(Number))
            #if EnglishName != self.EnglishName: ErrorLog("EnglishName not equal in table and tmm:"+EnglishName+"::"+self.EnglishName+"::"+str(Number))
            if abs(Year-self.Year) >= 2       : ErrorLog("Year        not equal in table and tmm:"+str(Year)  +"::"+str(self.Year)+"::"+str(Number))
            if abs(Min-self.Min) >= 5         : ErrorLog("Min         not equal in table and tmm:"+str(Min)   +"::"+str(self.Min)+"::"+str(Number)+":"+self.Name)
            if imdbID      != self.imdbID     : ErrorLog("imdbID      not equal in table and tmm:"+imdbID     +"::"+self.imdbID+"::"+str(Number))
            if Genre       != self.Genre      : ErrorLog("Genre       not equal in table and tmm:"+Genre      +"::"+self.Genre+"::"+str(Number))            

            #imdbID和Genre以tmm中的为准
            if imdbID      != self.imdbID     : tUpdated += 1; imdbID = self.imdbID
            if Genre       != self.Genre      : tUpdated += 1; Genre  = self.Genre                
            if tUpdated >= 1:
                up_sql = "UPDATE movies set  imdbID=%s,Genre=%s where Number=%s and copy=%s"
                up_val = (imdbID, Genre, Number, Copy)            
                try:
                    g_MyCursor.execute(up_sql,up_val)
                    g_DB.commit()
                except:
                    ErrorLog("failed to update imdbID and genre:"+imdbID+"::"+Genre+"::"+str(Number)+"::"+str(Copy))
                    return ERROR
                else:
                    ErrorLog(          "update imdbID and genre:"+imdbID+"::"+Genre+"::"+str(Number)+"::"+str(Copy))
                    return UPDATE
            return NOCHANGE
            
            
def CheckDiskMovie(DiskPath):
    '''
    对DiskPath下的每一个DirName加入对象实体到MyMovies[]并调用movie.CheckMovie()进行检查和处理，包括
    1)检查目录名称(CheckDirName)
    2)检查内容(CheckDirCont)
    3)进行目录重命名(RenameDirName)
    '''
    global g_MyMovies
    global g_Count
    
    if not os.path.isdir(DiskPath) :  DebugLog(DiskPath+"is not  a dir"); return -1
    for file in os.listdir(DiskPath):
        fullpathfile = os.path.join(DiskPath,file)
        if os.path.isdir(fullpathfile):
        
            #一些特殊文件夹忽略
            if file      == 'lost+found' or \
               file[0:6] == '.Trash' or \
               file[0:8] == '$RECYCLE' or\
               file[0:6] == 'System' or\
               file[0:4] == '0000':
                print ("ignore some dir:"+file)
                DebugLog ("ignore some dir:"+file)
                continue 

            g_MyMovies.append(movie.Movie(DiskPath,file))
            if g_MyMovies[g_Count].CheckMovie() == 0:
                DebugLog ("CheckMovie error:"+g_MyMovies[g_Count].DirName)
                DebugLog ("")
                DebugLog ("")
            else:
                DebugLog ("CheckMovie correct:"+g_MyMovies[g_Count].DirName)                
            g_Count += 1
        
    return 1
    
def CreateLink(tMovie,Disk):

    if tMovie.Collection == 1:
        i = 0
        while i < len(tMovie.SubMovie):
            CreateLink(tMovie.SubMovie[i],Disk)
            i += 1
        return 1
    
    if tMovie.Name == "" or tMovie.EnglishName == "" or tMovie.Year <= 1900 :
        print("invalid movie:"+tMovie.DirName)
        return 0
    
    #重新组装一下目录名
    DirName = tMovie.Name+'('+str(tMovie.Year)+')'+'('
    if tMovie.Source != "": DirName += '.'+tMovie.Source 
    if tMovie.Radio  != "": DirName += '.'+tMovie.Radio
    if tMovie.Compress != "": DirName += '.'+tMovie.Compress
    if tMovie.Audio  != "": DirName += '.'+tMovie.Audio
    DirName += '-'+str(tMovie.Number).zfill(4)+'-'+str(tMovie.Copy) +')'
    #if tMovie.Track  != "": DirName += '.'+tMovie.Track
    #if tMovie.ZipGroup != "": DirName += '.'+tMovie.ZipGroup

    if tMovie.Type == 0 :
        destdir=os.path.join(os.path.join(LinkDir,Disk),DirName)
    else:
        destdir=os.path.join(os.path.join(LinkDir,"tv"),DirName)
    if os.path.exists(destdir):
        pass
        #print(destdir+" existed")
    else:
        print("creat dir:"+destdir)
        try:
            os.mkdir(destdir)
        except:
            print("failed to create dir:"+destdir)
            return 0
        

    SrcDir = os.path.join(tMovie.DirPath,tMovie.DirName)
    for tempfile in os.listdir(SrcDir):
        if tempfile[:2] == 'SP' : continue
        if tempfile[-4:] == '.mkv' or\
           tempfile[-4:] == '.mp4' or\
           tempfile[-4:] == '.avi' or\
           tempfile[-3:] == '.ts' :
            srcfullfile=os.path.join(SrcDir,tempfile)
            destfullfile=os.path.join(destdir,tempfile)
            if os.path.islink(destfullfile):
                pass
                #print(destfullfile+" existed")
            else:
                try:
                    os.symlink(srcfullfile,destfullfile)
                except:
                    print("failed to link:"+srcfullfile+" to "+destfullfile)
                    return 0
    #write checktime and number+copy
    FileName=(str(tMovie.Number)).zfill(4)+'-'+str(tMovie.Copy)+".txt"
    fullFileName = os.path.join(destdir,FileName)
    if os.path.isfile(fullFileName):
        try:
            os.remove(fullFileName)
        except:
            print("failed to remove :"+fullFileName)
            return 0

    fo = open(fullFileName,"w+")
    fo.write(gCheckTime)
    fo.close()
    
    return 1
  
def CheckLinkDir(MovieDir):
  
    DebugLog("begin check link dir:"+MovieDir)
    #从MovieDir中获取Number和Copy
    CopyStr = MovieDir[-2:-1]
    NumberStr = MovieDir[-7:-3]
    if not(NumberStr.isdigit() and CopyStr.isdigit()) : ErrorLog("Number or copy is not valid:"+MovieDir); return -1
    Copy = int(CopyStr)
    Number = int(NumberStr)
    tempfulldir = os.path.join(os.path.join(LinkDir,g_CheckDisk),MovieDir)
    if not os.path.isdir(tempfulldir): ErrorLog("error:not a dir->"+tempfulldir); return -1
    
    #首先检查checktime
    temptxt = NumberStr+'-'+CopyStr+'.txt'
    temptxtfile = os.path.join(tempfulldir,temptxt)
    try:
        line = open(temptxtfile).read()
    except:
        ErrorLog(temptxt+" does not exist")
        return 0
    if line[:len(gCheckTime)] != gCheckTime: 
        ErrorLog(tempfulldir+" is not useful, delete it")
        try:
            shutil.rmtree(tempfulldir)
        except:
            ErrorLog("failed to rmtree :"+tempfulldir)
        return 0

    NfoFile = []
    for tempfile in os.listdir(tempfulldir):
        tempfullfile = os.path.join(tempfulldir,tempfile)       
        #删除空链接
        #删除SP开头链接 
        if os.path.islink(tempfullfile):
            if not os.path.isfile(os.path.realpath(tempfullfile)) or tempfile[:2] == 'SP' :
                try :
                    os.remove(tempfullfile)
                except:
                    ErrorLog("failed to remove empty link:"+tempfile)
                else:
                    DebugLog("removed empty link:"+tempfile)
        if tempfile[-3:] == "nfo" : NfoFile.append(tempfile)
        

    #从MovieDir中获取Name和Year
    Begin = 0; Year = 0
    while True:
        tIndex = MovieDir.find('(',Begin)
        if tIndex == -1 : break
        YearStr = MovieDir[tIndex+1:tIndex+5]
        if YearStr.isdigit():
            tYear = int(YearStr)
            if tYear >= 1900 and tYear <= int(gCheckTime[:4]) : 
                DebugLog("find  year:"+YearStr)
                Year = tYear
                break
        Begin = tIndex+1
    if Year == 0: ErrorLog("failed to find year:"+MovieDir); return -1
    Name = MovieDir[:tIndex]

    #读取movie.nfo
    if   len(NfoFile) >= 2: ErrorLog("2+ nfo file:"+MovieDir); return -1
    elif len(NfoFile) == 0: ErrorLog("no nfo file:"+MovieDir); return -1
    else:
        MovieNfoFile = os.path.join(tempfulldir,NfoFile[0])
        tTMMInfo = TMMInfo(Number,Copy,MovieNfoFile) 
        if tTMMInfo.ReadMovieNfo() == -1 : ErrorLog("failed to read movie.nfo"+MovieDir); return -1
    
    #比对Name和year
    if abs(tTMMInfo.Year-Year) >= 2: ErrorLog("Year: movie.nfo not equal dirname" +MovieDir )
    if tTMMInfo.Name.find(Name) < 0 and Name.find(tTMMInfo.Name) < 0 : ErrorLog("Name: movie.nfo not equal dirname" +MovieDir )
    
    tTMMInfo.UpdateTable()
    print("complete check dir:"+tempfulldir)

    
if __name__ == '__main__' :
    global g_MyCursor

    LogClear(DebugLogFile)
    LogClear(ErrorLogFile)

    #全局变量
    g_DB = mysql.connector.connect(
      host="localhost",      # 数据库主机地址
      user="dummy",    # 数据库用户名
      passwd="" ,  # 数据库密码
      database="db_movies"
    )
    g_MyCursor = g_DB.cursor()
    
    if len(sys.argv) == 1:
        print ("please choose the diskpath:")
        print ("0       == /media/root/BT/movies")
        print ("bt      == /media/root/BT/movies")
        print ("1       == /media/root/wd4t")
        print ("wd4t    == /media/root/wd4t")
        print ("2       == /media/root/wd2t")
        print ("wd2t    == /media/root/wd2t")
        print ("3       == /media/root/wd2t-2")
        print ("wd2t-2  == /media/root/wd2t-2")
        print ("4       == /media/root/sg3t")
        print ("sg3t    == /media/root/sg3t")
        print ("5       == /media/root/sg3t-2")
        print ("sg3t-2  == /media/root/sg3t-2")
        print ("6       == /media/root/SG8T")
        print ("sg8t    == /media/root/SG8T")
        Choise = input("your choise is :")
        print (Choise) 
    elif len(sys.argv) == 2:    
        Choise = sys.argv[1]
    else:
        print ("too many argv:")
        exit()
        
    if Choise == "0" or Choise.lower() == "bt":
        g_CheckDiskPath = "/media/root/BT/movies" ; g_CheckDisk = "BT"
    elif Choise == "1" or Choise.lower() == "wd4t" :
        g_CheckDiskPath = "/media/root/wd4t" ; g_CheckDisk = "wd4t"
    elif Choise == "2" or Choise.lower() == "wd2t" :
        g_CheckDiskPath = "/media/root/WD2T" ; g_CheckDisk = "wd2t"
    elif Choise == "3" or Choise.lower() == "wd2t-2" :
        g_CheckDiskPath = "/media/root/WD2T-2" ; g_CheckDisk = "wd2t-2"
    elif Choise == "4" or Choise.lower() == "sg3t" :
        g_CheckDiskPath = "/media/root/SG3T" ; g_CheckDisk = "sg3t"
    elif Choise == "5" or Choise.lower() == "sg3t-2" :
        g_CheckDiskPath = "/media/root/sg3t-2" ; g_CheckDisk = "sg3t-2"
    elif Choise == "6" or Choise.lower() == "sg8t" :
        g_CheckDiskPath = "/media/root/SG8T" ; g_CheckDisk = "sg8t"
    else :
        g_CheckDiskPath = Choise ; g_CheckDisk = ""
        print ("your choise is :"+Choise)

    #检查g_CheckDisk下所有的目录，加入g_MyMovies列表
    movie.Movie.ErrorLogFile  =  ErrorLogFile
    movie.Movie.ExecLogFile  =  ExecLogFile
    movie.Movie.DebugLogFile  =  DebugLogFile
    movie.Movie.ToBeExecDirName  =  ToBeExecDirName
    movie.Movie.ToBeExecRmdir  =  ToBeExecRmdir               
    if not os.path.isdir(g_CheckDiskPath) :  print(g_CheckDiskPath+"is not  a dir"); exit()
    print("begin check disk:"+g_CheckDiskPath)
    if CheckDiskMovie(g_CheckDiskPath) == -1 : exit()
    
    #创建链接
    print("begin create link:"+os.path.join(LinkDir,g_CheckDisk))
    tCurrentTime = datetime.datetime.now()
    gCheckTime=tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')
    i=0
    while i < len(g_MyMovies): 
        CreateLink(g_MyMovies[i],g_CheckDisk)
        i += 1

    #检查链接目录(例:e52/movies/wd4t下的信息
    Choise = input("do you want to check linkdir:"+g_CheckDisk+",y/n:")
    if Choise.lower() != "y" and Choise.lower() != "yes": print("exit now"); exit()

    destdir = os.path.join(LinkDir, g_CheckDisk)
    print("begin check linkdir:"+destdir)    
    if not os.path.isdir(destdir) : ErrorLog(destdir+" is not dir")
    for tempdir in os.listdir(destdir): CheckLinkDir(tempdir)

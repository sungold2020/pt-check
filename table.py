#!/usr/bin/python3
# coding=utf-8
import os
import sys
import shutil
import re
import datetime
import movie
import mysql.connector

ToBeExecDirName = False     # DirName名称
ToBeExecRmdir   = False     # 从子文件夹将内容提上来 删除空子目录
DebugLogFile = "log/debug3.log"             #日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/error3.log"             #错误日志
ExecLogFile  = "log/exec3.log"
CHECKERROR = -1
CHECKNORMAL = 0
g_MyMovies = []
g_Count = 0
g_CheckDiskPath = ""
g_CheckDisk = ""

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
               file[0:5] == 'cover' or\
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




def CheckTable(tMovie,tDisk)   :
    """
    对tMovie信息，进行插入表或者更新
    返回值：
        CHECKERROR  错误
        
    """
    if tMovie.Collection == 1:
        i = 0
        while i < len(tMovie.SubMovie):
            CheckTable(tMovie.SubMovie[i],tDisk)
            i += 1
        return 1
        
    if tMovie.Number < 0 or tMovie.Copy < 0 : ErrorLog("Number error:"+str(tMovie.Number)+"::"+str(tMovie.Copy)); return CHECKERROR
    
    #select from movies where Number == tMovie.Number and Copy == tMovie.Copy
    se_sql = "select \
        Nation,Type,Name,Min,FormatStr,DirName,Jpg,Nfo,NumberOfSP,NumberOfVideo,EnglishName,Year,Radio,Version,NationVersion,Special,Source,Compress,Audio,Track,Bit,HDR,ZipGroup,Deleted,Disk\
        from movies where Number=%s and Copy=%s"
    se_val = (tMovie.Number,tMovie.Copy)    
    g_MyCursor.execute(se_sql,se_val)
    tSelectResult = g_MyCursor.fetchall()
    #假如不存在就insert
    if len(tSelectResult) == 0: 
        Number = tMovie.Number
        Copy = tMovie.Copy
        Nation = tMovie.Nation
        Type = tMovie.Type
        Name = tMovie.Name
        Min = tMovie.Min
        FormatStr = tMovie.FormatStr
        DirName = tMovie.DirName
        Jpg = tMovie.Jpg
        Nfo = tMovie.Nfo
        NumberOfSP = tMovie.NumberOfSP
        NumberOfVideo = tMovie.NumberOfVideo
        EnglishName = tMovie.EnglishName
        Year = tMovie.Year
        Radio = tMovie.Radio
        Version = tMovie.Version
        NationVersion = tMovie.NationVersion
        Special = tMovie.Special
        Source = tMovie.Source
        Compress = tMovie.Compress
        Audio = tMovie.Audio
        Track = tMovie.Track
        Bit = tMovie.Bit 
        HDR = tMovie.HDR 
        ZipGroup = tMovie.ZipGroup
        Deleted = 0
        Disk = tDisk
        UpdateTime = gCheckTime
        CheckTime = gCheckTime
        in_sql = "INSERT INTO movies \
                (Number,Copy,Nation,Type,Name,Min,FormatStr,DirName,Jpg,Nfo,NumberOfSP,NumberOfVideo,EnglishName,Year,Radio,Version,NationVersion,Special,Source,Compress,Audio,Track,Bit,HDR,ZipGroup,Deleted,Disk,UpdateTime,CheckTime) \
          VALUES(%s    ,%s  ,%s    ,%s   ,%s ,%s ,%s       ,%s      ,%s,%s ,%s        ,%s           ,%s         ,%s  ,%s   ,%s     ,%s           ,%s     ,%s    ,%s      ,%s   ,%s   ,%s ,%s ,%s      ,%s     ,%s  ,%s        ,%s )"
        in_val= (Number,Copy,Nation,Type,Name,Min,FormatStr,DirName,Jpg,Nfo,NumberOfSP,NumberOfVideo,EnglishName,Year,Radio,Version,NationVersion,Special,Source,Compress,Audio,Track,Bit,HDR,ZipGroup,Deleted,Disk,UpdateTime,CheckTime)
        try:
            g_MyCursor.execute(in_sql,in_val)
            g_DB.commit()
        except:
            ErrorLog("insert error:"+DirName)
            return CHECKERROR
        else:
            print("insert:"+DirName)
            DebugLog("insert:"+DirName)
            return CHECKNORMAL
    #已经存在就update
    elif len(tSelectResult) == 1:
        Nation        = tMovie.Nation;        
        Type          = tMovie.Type;         
        Name          = tMovie.Name;       
        Min           = tMovie.Min;        
        FormatStr     = tMovie.FormatStr;   
        DirName       = tMovie.DirName;     
        Jpg           = tMovie.Jpg;     
        Nfo           = tMovie.Nfo;   
        NumberOfSP    = tMovie.NumberOfSP;  
        NumberOfVideo = tMovie.NumberOfVideo;
        EnglishName   = tMovie.EnglishName;  
        Year          = tMovie.Year;     
        Radio         = tMovie.Radio;    
        Version       = tMovie.Version;  
        NationVersion = tMovie.NationVersion;
        Special       = tMovie.Special;  
        Source        = tMovie.Source;  
        Compress      = tMovie.Compress;  
        Audio         = tMovie.Audio;  
        Track         = tMovie.Track; 
        Bit           = tMovie.Bit;  
        HDR           = tMovie.HDR; 
        ZipGroup      = tMovie.ZipGroup;   
        Deleted       = 0;        
        Disk          = tDisk; 
        UpdateTime    = gCheckTime
        CheckTime     = gCheckTime
        Number         = tMovie.Number
        Copy          = tMovie.Copy
        
        tUpdated = 0; tSelect = tSelectResult[0]
        if Nation        != tSelect[0] : tUpdated += 1
        if Type          != tSelect[1] : tUpdated += 1
        if Name          != tSelect[2] : tUpdated += 1
        if Min           != tSelect[3] : tUpdated += 1
        if FormatStr     != tSelect[4] : tUpdated += 1
        if DirName       != tSelect[5] : tUpdated += 1
        if Jpg           != tSelect[6] : tUpdated += 1
        if Nfo           != tSelect[7] : tUpdated += 1
        if NumberOfSP    != tSelect[8] : tUpdated += 1
        if NumberOfVideo != tSelect[9] : tUpdated += 1
        if EnglishName   != tSelect[10] : tUpdated += 1
        if Year          != tSelect[11] : tUpdated += 1
        if Radio         != tSelect[12] : tUpdated += 1
        if Version       != tSelect[13] : tUpdated += 1
        if NationVersion != tSelect[14] : tUpdated += 1
        if Special       != tSelect[15] : tUpdated += 1
        if Source        != tSelect[16] : tUpdated += 1
        if Compress      != tSelect[17] : tUpdated += 1
        if Audio         != tSelect[18] : tUpdated += 1
        if Track         != tSelect[19] : tUpdated += 1
        if Bit           != tSelect[20] : tUpdated += 1
        if HDR           != tSelect[21] : tUpdated += 1
        if ZipGroup      != tSelect[22] : tUpdated += 1  
        if Deleted       != tSelect[23] : tUpdated += 1
        if Disk          != tSelect[24] : tUpdated += 1        

        if Nation        != tSelect[0] : print("Nation: new="+Nation+"::"+tSelect[0])
        if Type          != tSelect[1] : print("Type: new="+str(Type)+"::"+str(tSelect[1]))
        if Name          != tSelect[2] : print("Name: new="+Name+"::"+tSelect[2])
        if Min           != tSelect[3] : print("Min: new="+str(Min)+"::"+str(tSelect[3]))
        if FormatStr     != tSelect[4] : print("FormatStr: new="+FormatStr+"::"+tSelect[4])
        if DirName       != tSelect[5] : print("DirName: new="+DirName+"::"+tSelect[5])
        if Jpg           != tSelect[6] : print("Jpg: new="+str(Jpg)+"::"+str(tSelect[6]))
        if Nfo           != tSelect[7] : print("Nfo: new="+str(Nfo)+"::"+str(tSelect[7]))
        if NumberOfSP    != tSelect[8] : print("NumberOfSP: new="+str(NumberOfSP)+"::"+str(tSelect[8]))
        if NumberOfVideo != tSelect[9] : print("NumberOfVideo: new="+str(NumberOfVideo)+"::"+str(tSelect[9]))
        if EnglishName   != tSelect[10] : print("EnglishName: new="+EnglishName+"::"+tSelect[10])
        if Year          != tSelect[11] : print("Year: new="+str(Year)+"::"+str(tSelect[11]))
        if Radio         != tSelect[12] : print("Radio: new="+Radio+"::"+tSelect[12])
        if Version       != tSelect[13] : print("Version: new="+Version+"::"+tSelect[13])
        if NationVersion != tSelect[14] : print("NationVersion: new="+NationVersion+"::"+tSelect[14])
        if Special       != tSelect[15] : print("Special: new="+Special+"::"+tSelect[15])
        if Source        != tSelect[16] : print("Source: new="+Source+"::"+tSelect[16])
        if Compress      != tSelect[17] : print("Compress: new="+Compress+"::"+tSelect[17])
        if Audio         != tSelect[18] : print("Audio: new="+Audio+"::"+tSelect[18])
        if Track         != tSelect[19] : print("Track: new="+Track+"::"+tSelect[19])
        if Bit           != tSelect[20] : print("Bit: new="+Bit+"::"+tSelect[20])
        if HDR           != tSelect[21] : print("HDR: new="+HDR+"::"+tSelect[21])
        if ZipGroup      != tSelect[22] : print("ZipGroup: new="+ZipGroup+"::"+tSelect[22])
        if Deleted       != tSelect[23] : print("Deleted: new="+str(Deleted)+"::"+str(tSelect[23]))
        if Disk          != tSelect[24] : print("Disk: new="+Disk+"::"+tSelect[24])        
        if Name != tSelect[2] :
            #序号相同，但名字不同，则有可能是序号重复了（小概率是修改名字了），仍然继续更新，但记录错误日志，待手工核实
            ErrorLog("Warning update New DirName:"+DirName)
            ErrorLog("               old DirName:"+tSelect[5])
            #return CHECKERROR
            
        if tUpdated >= 1:
            up_sql = "UPDATE movies set \
                    Nation=%s,\
                    Type=%s,\
                    Name=%s,\
                    Min=%s,\
                    FormatStr=%s,\
                    DirName=%s,\
                    Jpg=%s,\
                    Nfo=%s,\
                    NumberOfSP=%s,\
                    NumberOfVideo=%s,\
                    EnglishName=%s,\
                    Year=%s,\
                    Radio=%s,\
                    Version=%s,\
                    NationVersion=%s,\
                    Special=%s,\
                    Source=%s,\
                    Compress=%s,\
                    Audio=%s,\
                    Track=%s,\
                    Bit=%s,\
                    HDR=%s,\
                    ZipGroup=%s,\
                    Deleted=%s,\
                    Disk=%s,\
                    UpdateTime=%s,\
                    CheckTime=%s \
                    where Number=%s and copy=%s"
            up_val = (\
                    Nation,\
                    Type,\
                    Name,\
                    Min,\
                    FormatStr,\
                    DirName,\
                    Jpg,\
                    Nfo,\
                    NumberOfSP,\
                    NumberOfVideo,\
                    EnglishName,\
                    Year,\
                    Radio,\
                    Version,\
                    NationVersion,\
                    Special,\
                    Source,\
                    Compress,\
                    Audio,\
                    Track,\
                    Bit,\
                    HDR,\
                    ZipGroup,\
                    Deleted,\
                    Disk,\
                    UpdateTime,\
                    CheckTime,\
                    Number, Copy)            
        else:
            up_sql = "UPDATE movies set CheckTime = %s where Number= %s and Copy = %s"
            up_val = (CheckTime,Number,Copy)
        try:
            g_MyCursor.execute(up_sql,up_val)
            g_DB.commit()
        except:
            ErrorLog("update error:"+DirName+":"+up_sql)
            return CHECKERROR
        else:
            if tUpdated >= 1:
                print("update:"+DirName)
                DebugLog("update:"+DirName+" ::where Number="+str(Number).zfill(4)+"and Copy="+str(Copy))
            else:
                DebugLog("update checktime:"+DirName)
            return CHECKNORMAL
    else : ErrorLog("2+ result:"+str(tMovie.Number)+"::"+str(tMovie.Copy)); return CHECKERROR
        
def CheckDiskTable(DiskPath,Disk):
    '''
    首先，对Disk下的目录名称逐一进行检查分析后，继续数据库操作。
    1)调用CheckDirName()获取DirName并分析
    2)调用SplitFormat()进行格式分析
    3)调用CheckTable()进行数据库操作插入及更新
    
    最后，对该表Disk=Disk的Deleted等于0的进行Deleted置位（因为CheckTable()会对所有记录置位CheckTime为gCheckTime，那么没有置位的要么是已经删除，要么是转移到其他磁盘）
    '''
    #先要调用CheckDiskMovie，获得完整的g_MyMovies列表
    if CheckDiskMovie(DiskPath) == -1 : return -1
    
    i=0
    while i < len(g_MyMovies):
        CheckTable(g_MyMovies[i],Disk)
        i += 1
    
    #对Disk=Disk，CheckTime != gCheckTime的所有记录进行set Delete=1
    up_sql = "UPDATE movies set Deleted = 1 ,CheckTime = %s where Disk = %s and CheckTime!= %s and Deleted = 0"
    up_val = (gCheckTime,Disk,gCheckTime)
    try:
        g_MyCursor.execute(up_sql,up_val)
        g_DB.commit()
    except:
        ErrorLog("update error:"+up_sql)
        return CHECKERROR
    
    #找出所有刚被置位的记录，记录日志
    #select from movies where Number == tMovie.Number and Copy == tMovie.Copy
    se_sql = "select DirName from movies where Deleted = 1 and Disk = %s and CheckTime = %s"
    se_val = (Disk,gCheckTime)    
    g_MyCursor.execute(se_sql,se_val)
    tSelectResult = g_MyCursor.fetchall()    
    for tSelect in tSelectResult:
        ErrorLog("warning:set deleted=1:"+tSelect[0])
    DebugLog(str(len(tSelectResult))+" records deleted:"+Disk)
    
    se_sql = "select imdbid,dirname,number from movies where deleted=0"
    g_MyCursor.execute(se_sql)
    tSelectResult = g_MyCursor.fetchall()
    
    i = 0
    while i < len(tSelectResult):
        imdbID  = tSelectResult[i][0]
        DirName = tSelectResult[i][1]
        Number  = tSelectResult[i][2]
        if imdbID == "":  i+=1 ; continue
        j=i
        while j < len(tSelectResult):
            imdbID2  = tSelectResult[j][0]
            DirName2 = tSelectResult[j][1]
            Number2  = tSelectResult[j][2]
            if imdbID == imdbID2 and Number != Number2 :
                print("duplicate :"+tSelectResult[i][1])
                print("           "+tSelectResult[j][1])
            j+=1
        i+=1
        
if __name__ == '__main__' :
    global g_DB
    global g_MyCursor
    global gCheckTime

    #全局变量
    g_DB = mysql.connector.connect(
      host="localhost",      # 数据库主机地址
      user="dummy",    # 数据库用户名
      passwd="" ,  # 数据库密码
      database="db_movies"
    )
    g_MyCursor = g_DB.cursor()
    
    LogClear(ErrorLogFile)  
    LogClear(DebugLogFile)  
    LogClear(ExecLogFile)  
    
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
        print ("7       == /media/root/BT/tobe")
        print ("tobe    == /media/root/BT/tobe")
        Choise = input("your choise is :")
        print (Choise) 
    elif len(sys.argv) == 2:    
        Choise = sys.argv[1]
    else :
        print ("too many argv:")
        exit()
        
    if Choise == "0" or Choise.lower() == "bt":
        CheckDiskPath = "/media/root/BT/movies" ; disk = "BT"
    elif Choise == "1" or Choise.lower() == "wd4t" :
        CheckDiskPath = "/media/root/wd4t" ; Disk = "wd4t"
    elif Choise == "2" or Choise.lower() == "wd2t" :
        CheckDiskPath = "/media/root/WD2T" ; Disk = "wd2t"
    elif Choise == "3" or Choise.lower() == "wd2t-2" :
        CheckDiskPath = "/media/root/WD2T-2" ; Disk = "wd2t-2"
    elif Choise == "4" or Choise.lower() == "sg3t" :
        CheckDiskPath = "/media/root/SG3T" ; Disk = "sg3t"
    elif Choise == "5" or Choise.lower() == "sg3t-2" :
        CheckDiskPath = "/media/root/sg3t-2" ; Disk = "sg3t-2"
    elif Choise == "6" or Choise.lower() == "sg8t" :
        CheckDiskPath = "/media/root/SG8T" ; Disk = "sg8t"
    elif Choise == '7' or Choise.lower() == 'tobe' :
        CheckDiskPath = "/media/root/BT/tobe"; Disk = "tobe"
    else :
        print ("your choise is invalid:"+Choise)
        exit()
    
    movie.Movie.ErrorLogFile  =  ErrorLogFile
    movie.Movie.ExecLogFile  =  ExecLogFile
    movie.Movie.DebugLogFile  =  DebugLogFile
    movie.Movie.ToBeExecDirName  =  ToBeExecDirName
    movie.Movie.ToBeExecRmdir  =  ToBeExecRmdir
               
    print ("begin check "+Disk+" in table_movies")
    #获取CheckTime为当前时间
    tCurrentTime = datetime.datetime.now()
    gCheckTime=tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')
    g_MyMovies = []; g_Count = 0
    CheckDiskTable(CheckDiskPath,Disk)
    print ("complete check "+Disk+" in table_movies")    

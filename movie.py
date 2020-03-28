#!/usr/bin/python3
# coding=utf-8
import os
import re
import sys
import shutil
import datetime
#import mysql.connector
from pathlib import Path

SRC_NOT_DIR       = -1
DEST_NOT_DIR      = -2
DEPTH_ERROR       = -3
UNKNOWN_FILE_TYPE = -4
FAILED_MOVE       = -5
FAILED_RMDIR      = -6
SUCCESS           = 1    
"""
修订记录：
1、2020-03-15:V1.0 ，不足：1、ToBeExec的设定不应该留在movie.py中。2、日志需要重新设定
2、2020-03-17：V1.1，
    1、修改日志格式
    2、新增repack的格式参数
"""


def MoveDirFile(SrcDir,DestDir) :
    """
    将SrcDir所有文件移到DestDir目录中
    返回值：
    SRC_NOT_DIR
    DEST_NOT_DIR
    DEPTH_ERROR
    UNKNOWN_FILE_TYPE
    FAILED_MOVE
    FAILED_RMDIR
    """
    if not os.path.isdir(SrcDir) :  return SRC_NOT_DIR
    if not os.path.isdir(DestDir) : return DEST_NOT_DIR
    
    NumberOfFile = 0
    FileName = []
    for file in os.listdir(SrcDir):
        FullPathFile = os.path.join(SrcDir,file)
        if os.path.isdir(FullPathFile): return DEPTH_ERROR
        elif os.path.isfile(FullPathFile):
            NumberOfFile += 1
            FileName.append(FullPathFile)
        else: return UNKNOWN_FILE_TYPE
    
    #if Movie.ToBeExecRmdir == 0:
    #    self.ExecLog("mv from"+SrcDir)
    #    self.ExecLog("     to"+DestDir)
    #    return 1
        
    #逐个移动文件到目标文件夹
    i = 0
    while i < NumberOfFile :
        try:
            shutil.move(FileName[i],DestDir)
            i += 1
        except: 
            return FAILED_MOVE
    
    #删除这个空的srcDir
    try :
        os.rmdir(SrcDir)
    except:
        return FAILED_RMDIR

    return SUCCESS
    
#end def MoveDirFile

class Movie:
    '所有电影/连续剧的基类'
    Count = 0
    ErrorCount = 0
    
    #0表示测试，不执行修改，1表示执行修改
    ToBeExecDirName = False     # DirName名称
    ToBeExecRmdir   = False     # 从子文件夹将内容提上来 删除空子目录
    
    DebugLogFile=""
    ExecLogFile=""
    ErrorLogFile=""
     
    def __init__(self,DirPath,DirName):
        Movie.Count += 1
        
        # 目录名称组成部分
        self.Number = 0        #-1:error
        self.Copy = 0          #0表示正本，其他表示不同版本1:3D版，2:加长版
        self.Nation = ""       #
        self.Type = 0          #0:Movie 1:TV 2:Record
        self.Name = ""         #
        self.Min = 0
        self.FormatStr = "" 
        self.DirName = DirName

        self.DirPath = DirPath #确保DirPath结束符不带/
        self.DirNameToDo = 0   #目录名称是否要修改        
        self.Collection = 0    #是否为合集
        self.Number2 = 0       #合集下的第二个数字
        self.SubMovie = []     #合集下的对象
        self.SubMovieCount = 0 #合集下的目录数量
        
        # 目录内容组成部分
        self.Jpg = 0           #是否有海报图片 
        self.Nfo = 0           #是否有nfo文件
        self.NumberOfSP = 0    #花絮等的数量
        self.NumberOfVideo = 0 #不包含SP开头的视频文件，可能的几种情况
        # 0 :没有视频文件 
        # -1:有多个视频文件但不在定义的范围内 
        # >1:表示多个合集，可能发生的情况：
        #    1) 在纪录片和电视剧目录下，有效
        #    2) Part1/2,Disk1/2，任何两个文件名之间差别仅存在1个且为数字，有效
        #    3) 其他情况下，把它置为-1
        self.VideoFileName =[] # 保存video文件名在数组中
        self.SampleVideo = ""  #
        
        # 从格式中获取的信息
        self.EnglishName = ""  #英文片名（也可能是其他语种）
        self.Year = 0          #年份
        self.Radio = ""        #分辨率
        self.Version = ""      #版本，例如CC，DC
        self.NationVersion = "" #国家版本，如韩版，日版:JPN
        self.Special = ""     #特别说明，例如rerip
        self.Source = ""       #来源，如Blu-Ray，Web-DL
        self.Compress = ""     #压缩算法,如x264
        self.Audio = ""        #音频格式，如DTS
        self.Track = ""        #音轨，如2Audio 
        self.Bit = ""          #色彩精度，10bit,8bit
        self.HDR = ""          #HDR
        self.ZipGroup = ""     #压缩组
        
        self.IsError = 0       # 检查完以后是否有错误
    #end def __init__
      
    def Log(self,FileName,Str) :
        fo = open(FileName,"a+")
        #tCurrentTime = datetime.datetime.now()
        #fo.write(tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')+"::")
        fo.write(Str)
        fo.write('\n')
        fo.close()
    def DebugLog(self, Str):    
        self.Log(Movie.DebugLogFile,Str)
    def ExecLog(self,Str):
        self.DebugLog(Str)
        self.Log(Movie.ExecLogFile,Str)
    def ErrorLog(self,Str):
        print(Str)
        self.DebugLog(Str)
        self.Log(Movie.ErrorLogFile,Str)
    
    def CheckDirName(self):
        """
        #检查该目录名称格式是否合法，并分解出各元素
        # 正确的几种格式如下(包括合集)：
        # "Number-Nation-Name XXXMin Format"
        # "Number-Nation-Name Format"
        # "Number-Nation-Name XXXMin"
        # "Number-Nation-Name"
        # "Number-Nation-纪录片/电视剧-Name Format"
        # "Number-Nation-纪录片/电视剧-Name"
       
        # 合集的正确格式
        # "Number-Number-Nation-Name Format"
        # "Number-Number-Nation-Name"
        # 合集下标记IsCollection=1
       
        # "Name可以是多个名称，中间加-作为连接符，例如兄弟连-全10集
       
        """
       
        #self.DebugLog ("begin checkdirname:"+self.DirName)
        # 找出Number
        FindIndex = self.DirName.find("-")
        if FindIndex == -1 :  
            self.ErrorLog ("Error Number:" + self.DirName +"::") 
            self.IsError = 1 ;  return 0
        NumberStr = self.DirName[0:FindIndex]   
        Lest = self.DirName[FindIndex+1:]       

        
        if not(NumberStr.isdigit())  :#不是数字的话。
            self.ErrorLog ("invld Number1:"+self.DirName +"::"+NumberStr) 
            self.IsError = 1 ;  return 0
        self.Number = int(NumberStr)
        #self.DebugLog ("Number ="+str(self.Number))
        #self.DebugLog ("Lest ="+Lest)
        
        #加入NumberStr小于4，则需要补零，至self.DirNameToDo = 1，留给RenameDirName函数去补零
        if len(NumberStr) < 4: self.DirNameToDo = 1
        
        #继续找Nation或者Number2
        FindIndex = Lest.find("-")
        if FindIndex == -1 :  
            self.ErrorLog ("Error Nation:" + self.DirName +"::")
            self.IsError = 1 ;  return 0
        self.Nation = Lest[0:FindIndex]
        Lest = Lest[FindIndex+1:]
        #self.DebugLog ("Nation="+self.Nation)
        #self.DebugLog ("Lest="+Lest)
       
        
        #如果Nation是数字:
        #1、是一个0-9的数字，表面是Copy
        #2、是长度>=4的数字字符，则说明是合集，先找出Number2，然后才是Nation
        if self.Nation.isdigit() : 
            #Copy
            if len(self.Nation) == 1:
                self.Copy = int(self.Nation)
            #合集
            elif len(self.Nation) >= 4:
                self.Number2 = int(self.Nation)
                if self.Number2 <= self.Number : #合集的第二个数字应该大于第一个
                    self.ErrorLog ("Error Number2:"+self.DirName+"::"+self.Nation)
                    self.IsError = 1 ; return 0
                self.Collection = 1
            else:
                self.ErrorLog ("4- Number2:"+self.DirName+"::"+self.Nation)
                self.IsError = 1 ; return 0
                
            # 继续找Nation
            FindIndex = Lest.find("-")
            if FindIndex == -1 :
                self.ErrorLog ("Error Nation in Collection:" + self.DirName + "::" + Lest) 
                self.IsError = 1 ; return 0
            self.Nation = Lest[0:FindIndex]
            Lest = Lest[FindIndex+1:]
            
        #判断Nation长度
        if len(self.Nation) > 5 :
            self.ErrorLog ("5+length Nation:" + self.DirName + "::" + Lest) 
            self.IsError = 1 ; return 0
            
        # 如果前三个字符是电视剧或者纪录片
        if Lest[0:3] == "纪录片" :
            self.Type = 2
        elif Lest[0:3] == "电视剧" :
            self.Type = 1
        else :
            self.Type = 0
        if self.Type > 0:   #电视剧或者纪录片
            if Lest[3:4] != "-" :
                self.ErrorLog ("Error：not - :"+self.DirName)
                self.IsError = 1 ; return 0
            Lest = Lest[4:]
            
        #继续找Name
        FindIndex = Lest.find(" ")
        if FindIndex == -1 :  #说明Name后面就空了，没有Min和Format
            self.Name = Lest
            #self.DebugLog ("Name:"+self.Name)
            return 1    
        self.Name = Lest[0:FindIndex]
        Lest = Lest[FindIndex+1:]
        #self.DebugLog ("Name="+self.Name)
        #self.DebugLog ("Lest="+Lest)
        
        #继续找Min
        FindIndex = Lest.find("Min")
        if FindIndex == -1 :
            #self.DebugLog ("No Min:"+self.DirName)
            self.FormatStr = Lest
            return 1
        else:
            #Min后面没有了format
            if len(Lest) == FindIndex+3 :
                self.Min = int(Lest[0:FindIndex].lstrip())
                #self.DebugLog("no format after Min:"+self.DirName+"::"+str(self.Min))
                return 1
            #Min后的第一个字符是不是空格，如果不是表示Min可能是格式中的字符，例如Mind
            elif Lest[FindIndex+3:FindIndex+4] != ' ':
                #self.DebugLog ("Min之后不是空格:"+Lest[FindIndex+3:FindIndex+4]+"::"+self.DirName)
                self.FormatStr = Lest
            else :
                MinStr = Lest[0:FindIndex].lstrip() #Min之前的字符为MinStr,并去掉左边的空格符
                if not MinStr.isdigit() :
                    self.ErrorLog ("Invalid Min:"+self.DirName+"::"+MinStr)
                    self.IsError = 1 ; return 0
                self.Min = int(MinStr)
                self.FormatStr = Lest[FindIndex+4:]
                #self.DebugLog ("Min="+str(self.Min))
                #self.DebugLog ("Format="+self.FormatStr)
        
        if len(self.FormatStr) < 15:

            self.ErrorLog ("15- Format:"+self.DirName+self.FormatStr)
            self.IsError = 1; return 0
        
        return 1
    #end def CheckDirName    
        
    def RunTimeFromMkv(self):
        '''
        前置条件：
        1、已经执行过CheckDirCont
        2、有效的NumberOfViedeo，而且是MKV文件（其他格式暂不支持）
           如果是多个有效的Mkv，则叠加Min
        
        返回的是分钟数，如果为0表示错误
        '''

        if self.NumberOfVideo != 1 :
            #self.DebugLog ("not 1 video:"+self.DirName)
            return 0

        if (self.VideoFileName[0])[-3:] != "mkv" :
            #self.DebugLog ("not mkvfile:"+self.DirName)
            return 0

        Path = os.path.join(self.DirPath,self.DirName)
        MkvName = os.path.join(Path,self.VideoFileName[0])
        RunTimeStr='mkvinfo --ui-language en_US "'+MkvName+'" | grep Duration'
        #self.DebugLog (RunTimeStr)
        Line = os.popen(RunTimeStr).read()
        #self.DebugLog (Line[:24])
        Hour=Line[14:16]
        Min=Line[17:19]
        #self.DebugLog (Hour+" "+Min)
        if not ( Hour.isdigit() and Min.isdigit() ):
            #self.DebugLog ("Hour or Min isn't digit"+Hour+":"+Min)
            return 0

        MinNumber = int(Hour)*60 + int(Min)
        #self.DebugLog ("Min="+str(MinNumber))
        return MinNumber
    #End def RunTimeFromMkv 
    
    def FormatFromVideoFile(self):
        '''
        前置条件：
        1、已经执行过CheckDirCont
        2、有且只有一个有效的视频文件NumberOfVideo == 1
        
        成功将把self.FormatStr置为找到的格式，并且返回1
        否则返回0
        '''  
        
        if not self.NumberOfVideo == 1 :
            #self.DebugLog ("2+Video,don't know how to find format from video")
            return 0
        
        FileName = self.VideoFileName[0]
        Length = len(FileName)
        if FileName[-3:] == "mkv" or FileName[-3:] == "avi"or FileName[-3:] == "mp4":
            self.FormatStr = FileName[:Length-4]
            return 1
        elif FileName[-2:] == "ts":
            self.FormatStr = FileName[:Length-3]
            return 1
        else:
            return 0
    #end def FormatFromVideoFile    
    
    def RenameDirName(self):
        """
        前置条件：
        1、正确执行过CheckDirName,即已经把DirName分解出各元素
        2、正确执行过CheckDirCont，即该目录下有正确的视频文件，因为需要通过视频文件获取Min和Format
        
        如果DirName信息不准确或者不完整的话，尝试补充完成并修改
        一、持续检查各个元素，如果缺少尝试补充:
        1、元素出现错误，并且无法补充完成，记录错误日志并返回0
        2、无错误，也不需要补充修改，DirNameToDo=0，返回1
        3、无错误，补充修改完成，DirNameTodo = 1 
        二、DirNameTodo =1，尝试修改
        1、如果ToDoExecDirName=1，则进行修改:
            1）修改成功，返回1，并记录执行日志
            2）修改错误，返回0，并记录错误日志
        2、否则，记录执行日志（ToDo）
        """

        #self.DebugLog("begin RenameDirName")
        if self.Collection == 1 :
            self.ErrorLog("Error:it is collection in RenameDirName:"+self.DirName)
            self.IsError = 1; return 0
            
        if self.Number <= 0 or self.Number >= 10000 :
            self.ErrorLog("ErrorNumber:"+self.DirName+"::"+str(self.Number))
            self.IsError = 1 ; return 0
                   
        if  len(self.Nation) ==0 or len(self.Nation) >= 8 :
            self.ErrorLog("8+Nation :"+self.DirName+"::"+self.Nation )
            self.IsError = 1; return 0
            
        if len (self.Name) == 0 or len(self.Name) >= 20 :
            self.ErrorLog("20+Name :"+self.DirName+"::"+self.Name )
            self.IsError = 1; return 0
        
        #self.DebugLog (str(self.Min))
        MinFromMkv = self.RunTimeFromMkv()
        #self.DebugLog (str(MinFromMkv))
        if self.Min == 0 and self.Type == 0:
            if MinFromMkv == 0:
                self.ErrorLog("not Found Min:"+self.DirName)
                self.IsError = 1 ; return 0
            else:
                self.Min = MinFromMkv ; self.DirNameToDo = 1

        elif MinFromMkv != 0 and abs(self.Min-MinFromMkv) >= 2:
            self.Min = MinFromMkv ; self.DirNameToDo = 1
        else:
            pass
            
        self.FormatStr = self.FormatStr.strip()  #去掉前后空格
        self.DebugLog("Current formatstr;"+self.FormatStr)
        if len(self.FormatStr) == 0:
            #从video 文件名里提取出格式文件
            if self.FormatFromVideoFile() == 0:
                self.ErrorLog("not found Format:"+self.DirName)
                self.IsError = 1; return 0
            self.DebugLog("find Format:"+self.FormatStr)
            self.DirNameToDo = 1
        elif len(self.FormatStr) <= 10:
            self.ErrorLog("10-Format:"+self.DirName+"::"+self.FormatStr)
            self.IsError = 1; return 0
        else:
            self.DebugLog ("correct format"+self.FormatStr)
        
        #如果TODO=0，说明DirName不需要修改
        if self.DirNameToDo == 0 :
            self.DebugLog ("Correct DirName:"+self.DirName)
            return 1

        SourceDir = os.path.join(self.DirPath,self.DirName)
        NumberStr = (str(self.Number)).zfill(4)
        if self.Copy > 0:
            NumberStr = NumberStr + "-" + str(self.Copy)
        
        if self.Type == 0:
            DestDirName = NumberStr+"-"+self.Nation+"-"+self.Name+" "+str(self.Min)+"Min "+self.FormatStr
        elif self.Type == 1: 
            DestDirName = NumberStr+"-"+self.Nation+"-电视剧-"+self.Name+" "+self.FormatStr
        elif self.Type == 2:
            DestDirName = NumberStr+"-"+self.Nation+"-纪录片-"+self.Name+" "+self.FormatStr
        else:
            self.ErrorLog("Error Type:"+self.DirName+"::"+int(self.Type))
            self.IsError = 1; return 0
            
        DestDir = os.path.join(self.DirPath,DestDirName)
        
        self.DebugLog("begin rename dirname:")
        if Movie.ToBeExecDirName == True:
            try:
                os.rename(SourceDir,DestDir)
                self.ExecLog("mv "+self.DirName+'\n')
                self.ExecLog("   "+DestDirName+'\n')
                self.DebugLog ("rename success")
                return 1
            except:
                self.ErrorLog("mv failed:"+self.DirName+'\n')
                self.ErrorLog("          "+DestDirName)
                self.DebugLog ("Mv failed:"+SourceDir)
                self.DebugLog ("          "+DestDir)
                self.IsError = 1 ; return 0
        else:
            self.ExecLog("ToDo mv "+self.DirName+'\n')
            self.ExecLog("        "+DestDirName+'\n')
            return 1
    
    #end def RenameDirName
    
    
    def CheckDirCont(self) :
        '''
        前置条件:
        1、执行过CheckDirName，因为需要调用self.IsCollection
        2、不能是合集，如果是返回错误。
        
        检查目录下的内容，可能有效的几种情况:
        1、有且只有一个子目录，且子目录下不再有目录。则把子目录内容提取到上级目录。
        2、有srt/ info/ SP/的子目录（其他目录非法，报错）
        3、没有子目录
        
        1、Type为电视剧/纪录片下，目录中可以有多个视频文件
        2、Type为0，目录中只有一个视频文件
        3、Type为0，目录中有多个视频文件，但视频文件差别只有一个字符（且为数字），例如Disk1，Disk2
        4、忽略掉SP开头的视频文件（花絮等）
        5、发现有sample字样的视频文件，仅记录错误日志和标记在SampleVideo，待手工处理。以免误删
        
        6、有JPG海报文件，则拷贝poster/cover.jpg，无则标记Jpg=0，不影响检查和返回值
        '''

        if self.Collection == 1 :
            self.ErrorLog("Error:it is collection in CheckCont:"+self.DirName)
            self.IsError =1; return 0
            
        NumberOfSubDir = 0
        NumberOfFile = 0
        CoverJpg = 0
        PostJpg = 0
        SubDirName = ""      #仅当NumberOfSubDir=1才有意义
        JpgFileName = ""
        for File in os.listdir(os.path.join(self.DirPath,self.DirName)):
            FullPathFile = os.path.join(os.path.join(self.DirPath,self.DirName),File)
            if os.path.isdir(FullPathFile):
                if File[0:2] == "SP" or File[0:3] == "srt" or File[0:4] == "info" : # 忽略掉特殊文件夹
                    self.DebugLog ("it is SP/srt/info DIR:"+File)
                    continue
                if os.path.islink(FullPathFile) :
                    self.DebugLog ("it is a link:"+self.DirName)
                    continue 
                SubDirName = FullPathFile 
                NumberOfSubDir += 1
            elif os.path.isfile(FullPathFile):
                NumberOfFile += 1
                #视频文件
                if File[-3:] == "avi" or File[-3:] == "mkv" or File[-2:] == "ts" or File[-3:] == "mp4" :
                    if File[0:2] == "SP" :
                        self.DebugLog ("find SP video:"+File)
                        self.NumberOfSP += 1
                    elif re.search("sample",File,re.I):
                        self.DebugLog ("find sample video:"+File)
                        self.ErrorLog("sample video:"+File)  #仅记录，不做处理，待手工处理
                        self.SampleVideo = File 
                    else:
                        self.NumberOfVideo += 1
                        self.VideoFileName.append(File)
                #jpg海报文件
                elif File[-3:] == "jpg" :
                    if File == "cover.jpg":
                        CoverJpg = 1
                    elif File == "poster.jpg" :
                        PostJpg = 1
                    else :
                        JpgFileName = File
                elif File[-3:] == "nfo" :
                    self.Nfo = 1
                else:
                    self.DebugLog ("other type file"+File)
            else:
                self.ErrorLog("not file or dir :"+FullPathFile)
                self.IsError = 1; return 0
                
        if NumberOfSubDir == 1:   #除了srt/info/SP/之外有一个子目录
            if NumberOfFile == 0 :#除了一个子目录外没有其他文件
                SrcDir  = os.path.join(os.path.join(self.DirPath,self.DirName),SubDirName)
                DestDir = os.path.join(self.DirPath,self.DirName)
                if Movie.ToBeExecRmdir == True :
                    if MoveDirFile(SrcDir,DestDir) == SUCCESS:
                        self.ExecLog("mv "+SrcDir+" "+DestDir)
                        return self.CheckDirCont()   #已经移动文件夹成功，再重新检查
                    else:
                        self.ErrorLog("failed mv "+SrcDir+" "+DestDir)
                        self.IsError = 1; return 0                       
                else:
                    self.ExecLog("todo mv "+SrcDir+" "+DestDir)
                    self.IsError = 1; return 0
            else:  #试图删除这个空的子目录，如果不成功，说明不是空的，报错
                try :
                    os.rmdir(SubDirName)
                    self.ExecLog("rmdir "+SubDirName)
                except:
                    self.ErrorLog("one not empty subdir:"+SubDirName)
                    self.IsError = 1; return 0
        elif NumberOfSubDir > 1:
            self.ErrorLog("1+ subdir:"+self.DirName)
            self.IsError = 1; return 0
        else :
            self.DebugLog ("no subdir"+self.DirName)
        
        #检查海报
        CurrentPath = os.path.join(self.DirPath,self.DirName)
        if PostJpg == 1 :
            if CoverJpg == 0:
                try :
                    SrcFileName  = os.path.join(CurrentPath,"poster.jpg")
                    DestFileName = os.path.join(CurrentPath,"cover.jpg")
                    shutil.copyfile(SrcFileName,DestFileName)
                    self.ExecLog("cp poster.jpg cover.jpg in"+self.DirName)
                    self.Jpg = 1
                except:
                    self.ErrorLog("failed cp poster.jpg in"+self.DirName)
                    self.IsError = 1; return 0
            else:
                self.Jpg = 1
        elif CoverJpg == 1:   #没有poster.jpg但是有cover.jpg 
            try :
                SrcFileName  = os.path.join(CurrentPath,"cover.jpg")
                DestFileName = os.path.join(CurrentPath,"poster.jpg")
                shutil.copyfile(SrcFileName,DestFileName)
                self.ExecLog("cp cover.jpg in"+self.DirName)
                self.Jpg = 1
            except:
                self.ErrorLog("failed cp cover.jpg in"+self.DirName)
                self.DebugLog("failed cp cover.jpg in"+self.DirName)
                self.DebugLog(SrcFileName)
                self.DebugLog (DestFileName)
                self.IsError = 1; return 0
        elif JpgFileName != "" : #但是还有其他jpg文件
            try :
                SrcFileName  = os.path.join(CurrentPath,JpgFileName)
                DestFileName = os.path.join(CurrentPath,"poster.jpg")
                self.DebugLog ("To CP:"+SrcFileName)
                self.DebugLog ("      "+DestFileName)
                shutil.copyfile(SrcFileName,DestFileName)
                self.ExecLog("cp "+JpgFileName+" poster.jpg in"+self.DirName)
                DestFileName = os.path.join(CurrentPath,"cover.jpg")
                shutil.copyfile(SrcFileName,DestFileName)
                self.DebugLog ("      "+DestFileName)
                self.ExecLog("cp "+JpgFileName+" cover.jpg in"+self.DirName)
                self.Jpg = 1
            except:
                self.ErrorLog("failed cp "+JpgFileName+" in"+self.DirName)
                self.IsError = 1; return 0
        else:
            self.ErrorLog("no jpg file:"+self.DirName)
            self.Jpg = 0   #标记，但不返回，不影响后续检查操作
            
        # 检查视频文件
        if self.NumberOfVideo == 0:
            self.ErrorLog("no video in"+self.DirName)
            self.IsError = 1 ; return 0
        elif self.NumberOfVideo == 1:
            return 1
        else : #>=2忽略SP/sample外，还有多个视频文件，则需要进一步分析
            if self.Type == 1 or self.Type == 2 : #电视剧/纪录片
                pass
            else:
                #比较多个video名的差别，
                #如果长度一致，仅有一个字符的差别，且这个字符是数字。则OK，否则报错
                #先以第一个VideoFileName为比较对象，后面逐个VideoFileName和它比较
                length = len(self.VideoFileName[0])
                i = 1
                while i < self.NumberOfVideo :
                    if len(self.VideoFileName[i]) != length :
                        self.ErrorLog("diff len video:"+self.DirName)
                        self.DebugLog ("diff len video:"+self.DirName)
                        self.DebugLog ("  1:"+self.VideoFileName[0])
                        self.DebugLog ("  2:"+self.VideoFileName[i])
                        self.NumberOfVideo = -1
                        self.IsError = 1 ; return 0
                    
                    NumberOfDiff = 0 #不同字符的个数
                    SrcStr  = self.VideoFileName[0]
                    DestStr = self.VideoFileName[i]
                    j = 0
                    while j < length :
                        SrcChar  = SrcStr[j:j+1]
                        DestChar = DestStr[j:j+1]
                        if SrcChar != DestChar:
                            if SrcChar.isdigit() and DestChar.isdigit():
                                NumberOfDiff += 1
                            else :
                                #有不同的字符，且至少有一个不是数字，报错
                                self.ErrorLog("Diff Char Video:"+self.DirName)
                                self.DebugLog ("diff Char video:"+self.DirName)
                                self.DebugLog ("  1:"+self.VideoFileName[0])
                                self.DebugLog ("  2:"+self.VideoFileName[i])  
                                self.NumberOfVideo = -1
                                self.IsError = 1 ; return 0
                        j+=1
                    
                    if NumberOfDiff > 1:
                        self.ErrorLog("2+ diff video:"+DirName)
                        self.DebugLog ("2+diff video:"+DirName)
                        self.DebugLog ("  1:"+self.VideoFileName[0])
                        self.DebugLog ("  2:"+self.VideoFileName[i])
                        self.NumberOfVideo = -1
                        self.IsError = 1 ; return 0
                    i+=1
        #检查视频文件结束
    #end def CheckDirCont    
        
    
    def CheckMovie(self):
        '''
        在创建一个Movie对象后，执行检查。它将逐个调用selfDirName，CheckDirCont，RenameDirName
        
        如果目录是一个合集的话，它将标记Collection，然后创建SubMovie对象，并逐个检查
        '''
        
        if self.CheckDirName() == 0 :
            self.ErrorLog("failed CheckDirName:"+self.DirName)
            self.IsError = 1; return 0
        
        if self.Collection == 1:
            
            Movie.Count -= 1    # 这是一个合集目录，不应该计数
            
            self.DebugLog ("Begin Collection"+self.DirName)
            SubDirPath = os.path.join(self.DirPath,self.DirName)
            for File in os.listdir(SubDirPath):
                FullPathFile = os.path.join(SubDirPath,File)
                if os.path.isdir(FullPathFile):
                    self.SubMovie.append(Movie(SubDirPath,File))
                    self.SubMovie[-1].CheckMovie()
                    self.SubMovieCount += 1
            self.DebugLog ("End Collection"+self.DirName)
            if self.SubMovieCount > 0 :
                return 1
            else:
                self.ErrorLog ("empty Collection:"+self.DirName)
                self.IsError = 1 ; return 0
        #end if self.Collection == 1
        
        if self.CheckDirCont() == 0 :
            self.ErrorLog("failed CheckDirCont:"+self.DirName)
            self.IsError = 1; return 0
            
        if self.RenameDirName() == 0 :
            self.ErrorLog("failed RenameDirName:"+self.DirName)
            self.IsError = 1; return 0
        
        if self.SplitFormat() == 0:
            self.ErrorLog("SplitFormat:"+self.DirName)
            self.IsError = 1; return 0
        return 1
    #end def CheckMovie

    
    def SplitFormat(self):
    
        '''
        对Format进行分析，提取年份，分辨率，压缩算法等
    
        前置条件：
        FormatStr已经获取，最好在RenameDirName后执行 
        '''

        
        self.FormatStr = self.FormatStr.strip()
        if len(self.FormatStr) == 0 :
            self.ErrorLog ("no format:"+self.DirName)
            self.IsError = 1; return 0

        #尝试进行空格分割
        #SplitSign = ' '
        FormatList = (self.FormatStr).split()
        if len(FormatList) < 3:
            #再尝试进行'.'分割
            FormatList = (self.FormatStr).split('.')
            if len(FormatList) < 3:
                self.ErrorLog("3- format:"+self.FormatStr)
                self.IsError = 1; return 0
            #else :
            #SplitSign = '.'

        #处理最后一个group，通常是XXX-Group格式
        tStr = FormatList[-1]
        tIndex = tStr.rfind('-')
        if tIndex > 0:
            FormatList[-1] = tStr[:tIndex]
            self.ZipGroup = tStr[tIndex+1:]
        
        NumberOfElement=0  #找到了几个关键字
        LastIndex = -1     #找到关键字后要标记出它在FormatList中的索引
        FormatSign = []    #对应FormatList[]的标志位，0表示未识别，1表示已识别
        #beginfrom 1,0 must be englishname
        i=1 ; FormatSign.append(0)
        while i < len(FormatList) :
            self.DebugLog ("FormatList:i="+str(i)+"::"+FormatList[i])
            TempStr = FormatList[i].lower()
            TempStr = TempStr.replace(' ','')  #删除空格并把它全部转换为小写，便于比较
            FormatSign.append(0)
            
            #年份：
            if (TempStr.isdigit() and int(TempStr) > 1900 and int(TempStr) <= int(datetime.datetime.now().year)):
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Year = int(FormatList[i])
                self.DebugLog ("find Year:"+str(self.Year)+"i="+str(i))
            #版本
            elif TempStr == "cc" or \
                 TempStr == "dc" or \
                 TempStr == "extended" or \
                 TempStr == "open-matte" or \
                 TempStr == "the-final-cut" or\
                 TempStr == "uncut" or\
                 TempStr == "unrated" or \
                 TempStr == "complete" or\
                 TempStr == "cut":
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                if self.Version == "": self.Version = FormatList[i]
                else:                  self.Version += '-'+FormatList[i]
                self.DebugLog ("find Version:"+self.Version+"i="+str(i))
            #国家版本
            elif TempStr.upper() == "JPN" or \
                 TempStr.upper() == "GBR" or \
                 TempStr.upper() == "KOR" or \
                 TempStr.upper() == "USA" or \
                 TempStr.upper() == "FRA" or \
                 TempStr.upper() == "TW" or \
                 TempStr.upper() == "HK":
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.NationVersion = FormatList[i]
                self.DebugLog ("find NationVersion:"+self.NationVersion+"i="+str(i))
            #特别说明，例如rerip
            elif TempStr == "rerip" or TempStr == "repack":
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Special = FormatList[i]
                self.DebugLog ("find Special:"+self.Special+"i="+str(i))
            #分辨率
            elif TempStr == "720p" or \
                 TempStr == "1080p" or \
                 TempStr == "2160p" or \
                 TempStr == "1080i" or \
                 re.match("[0-9][0-9][0-9][0-9]x[0-9][0-9][0-9]p",TempStr) is not None or \
                 re.match("[0-9][0-9][0-9][0-9]x[0-9][0-9][0-9][0-9]p",TempStr) is not None:
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Radio = FormatList[i]
                self.DebugLog ("find Radio:"+self.Radio+"i="+str(i))
            #ignore 2d
            elif TempStr == "2d":   
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.DebugLog ("ignore 2d:"+"i="+str(i))
            #来源
            elif TempStr == "bluray" or \
                 TempStr == "blu-ray" or \
                 TempStr == "uhd" or \
                 TempStr == "3d" or\
                 TempStr == "sbs" or\
                 TempStr == "nf" or\
                 TempStr == "web-dl" or \
                 TempStr == "hdtv" :
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                if self.Source == "": self.Source = FormatList[i]
                else:                 self.Source += '-'+FormatList[i]
                self.DebugLog ("find Source:"+self.Source+"i="+str(i))
            #压缩算法
            elif TempStr == "x265.10bit" or \
                 TempStr == "x265 10bit" or \
                 TempStr == "x265-10bit" :
                NumberOfElement += 2 ; LastIndex = i ; FormatSign[i] = 1
                self.Compress = "x265" ; self.Bit = "10bit"
                self.DebugLog ("find Compress and bit：x265.10bit")
            elif TempStr == "x264" or \
                 TempStr == "h264" or \
                 TempStr == "x265" or \
                 TempStr == "h265" or \
                 TempStr == "avc" or \
                 TempStr == "hevc" :
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Compress = FormatList[i]
                self.DebugLog ("find Compress:"+self.Compress+"i="+str(i))
            #音频格式
            elif TempStr[0:3] == "dts" or \
                 TempStr[0:6] == "dts-hd" or \
                 TempStr[0:5] == "dtshd" or\
                 TempStr[0:3] == "ac3" or \
                 TempStr[0:3] == "aac" or \
                 TempStr[0:3] == "dd2" or \
                 TempStr[0:3] == "dd5" or \
                 TempStr[0:3] == "dda" or \
                 TempStr[0:3] == "ddp" or \
                 TempStr[0:4] == "lpcm" or \
                 TempStr[0:5] == "atmos" or \
                 TempStr[0:6] == "truehd" or \
                 TempStr[0:7] == "true-hd" or \
                 TempStr == "dd" :     
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Audio += FormatList[i]
                self.DebugLog ("find audio:"+self.Audio+"i="+str(i))
                
                #音频格式比较复杂，后面可能还有信息被分割成下一个组了
                #所以，需要继续识别后面的组元素是否要加入音频格式
                
                while 1 == 1 and i+1 < len(FormatList) :
                    TempStr2 = (FormatList[i+1]).replace(' ','')   #去掉空格
                    TempStr2 = TempStr2.replace('.','')            #去掉'.'号
                    if TempStr2 == 'MA' or \
                       TempStr2 == 'MA5' or \
                       TempStr2 == 'MA51' or \
                       TempStr2 == 'MA7' or \
                       TempStr2 == 'MA71' or \
                       TempStr2 == 'MA20' or \
                       TempStr2 == '20' or \
                       TempStr2 == '51' or \
                       TempStr2 == '71' or \
                       TempStr2 == '0' or \
                       TempStr2 == '1' or \
                       TempStr2 == '2' or \
                       TempStr2 == '5' or \
                       TempStr2 == '6' or \
                       TempStr2 == '7' :
                        i += 1; LastIndex = i; FormatSign.append(1)
                        self.Audio += FormatList[i]
                    else : #只要有一个不满足条件就跳出循环
                        break
                self.DebugLog ("find Audio-end："+self.Audio)
            #音轨，如2Audio
            elif TempStr[1:6] == "audio" :
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Track = FormatList[i]
                self.DebugLog ("find Track"+self.Track+"i="+str(i))
            #色彩精度，10bit
            elif TempStr == "10bit" or TempStr == "8bit" :
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.Bit = FormatList[i]
                self.DebugLog ("find bit ："+self.Bit+"i="+str(i))
            elif TempStr == "hdr" or\
                 TempStr == "hdr10" or\
                 TempStr == "hdrplus" or\
                 TempStr == "hdr10plus":
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                self.HDR = FormatList[i]
                self.DebugLog ("find hdr"+"i="+str(i))
            elif TempStr == "mnhd" or\
                 TempStr == "muhd" :
                NumberOfElement += 1 ; LastIndex = i ; FormatSign[i] = 1
                if self.ZipGroup == "" : self.ZipGroup = FormatList[i]
                else :                   self.ZipGroup = FormatList[i]+'-'+self.ZipGroup
                self.DebugLog ("ZipGroup:"+self.ZipGroup+" i="+str(i))
            else :
                pass 
            
            if NumberOfElement == 1 and self.EnglishName == "": #第一次识别出关键字，那么之前的就是片名了        
                if i == 0: #第一个分割字符就是关键字，说明没有找到片名
                    self.ErrorLog("no name:"+self.DirName)
                    self.IsError = 1; return 0
                j=0
                while j < i:
                    if j != 0 :
                        self.EnglishName += '.'
                    self.EnglishName += FormatList[j]
                    FormatSign[j] = 1
                    j += 1   
                self.DebugLog ("name="+self.EnglishName)
            i += 1
            
        #end while i < len(FormatList)
        
        #识别出的最后关键字为压缩组
        i=LastIndex+1
        while i < len(FormatSign) :
            if self.ZipGroup == "": self.ZipGroup = FormatList[i]
            else :                 self.ZipGroup = FormatList[i]+'-'+self.ZipGroup
            FormatSign[i] = 1
            i += 1
        self.DebugLog ("Group="+self.ZipGroup)
        
        #找出所有未识别的元素
        i = 0 ; Error = 0
        while i < len(FormatSign) :
            if FormatSign[i] == 0:
                self.DebugLog ("unknown word:"+FormatList[i])
                Error = 1
            i += 1
            
        if Error == 1:
            return 0
        
        #重新组装 FormatStr
        String = ""
        if self.EnglishName != "" : String += self.EnglishName+"."
        if self.Year != 0         : String += str(self.Year)+"."
        if self.NationVersion !="": String += self.NationVersion+"."
        if self.Version != ""     : String += self.Version+"."
        if self.Radio != ""       : String += self.Radio+"."
        if self.Special != ""     : String += self.Special+"."
        if self.Source != ""      : String += self.Source +"."
        if self.Compress != ""    : String += self.Compress+"."
        if self.Bit != ""         : String += self.Bit+"."
        if self.HDR !=  ""        : String += self.HDR+"."
        if self.Audio != ""       : String += self.Audio+"."
        if self.Track != ""       : String += self.Track+"."
        if self.ZipGroup != ""    : String += self.ZipGroup
        self.DebugLog("new format:"+String)
        #self.FormatStr = String
        return 1
    #end def SplitFormat()
    
#end class Movie


#!/usr/bin/python3
# coding=utf-8
import os
import re
import sys
import shutil
import datetime
#import mysql.connector
from pathlib import Path
import movie

"""
修订记录：
1、2020-03-15：V10，不足：log/movie的模块组织重新设定。2、一些运行参数提炼到文件开始
2、2020-03-17：V1.1
    1、新增日志修改
    2、check增加自定义文件夹入口
"""
#运行日志
ErrorLogFile="/root/py/log/checkerror.log"
ExecLogFile="/root/py/log/checkexec.log"
DebugLogFile="/root/py/log/checkdebug.log"
ToBeExecDirName = False     # DirName名称
ToBeExecRmdir   = False     # 从子文件夹将内容提上来 删除空子目录
    
#全局变量
g_MyMovies = []
g_Count = 0
g_CheckDiskPath = ""
g_CheckDisk = ""

def LogClear(FileName) :
    if os.path.isfile(FileName):
        if os.path.isfile(FileName+".old"):    os.remove(FileName+".old")
        os.rename(FileName,FileName+".old")
      

def CheckDiskMovie(DiskPath):
    '''
    对DiskPath下的每一个DirName加入对象实体到MyMovies[]并调用movie.CheckMovie()进行检查和处理，包括
    1)检查目录名称(CheckDirName)
    2)检查内容(CheckDirCont)
    3)进行目录重命名(RenameDirName)
    '''
    global g_MyMovies
    global g_Count
    
    if not os.path.isdir(DiskPath) :  print(DiskPath+"is not  a dir"); return -1
    for file in os.listdir(DiskPath):
        fullpathfile = os.path.join(DiskPath,file)
        if os.path.isdir(fullpathfile):
        
            #一些特殊文件夹忽略
            if file      == 'lost+found' or \
               file[0:6] == '.Trash' or \
               file[0:8] == '$RECYCLE' or\
               file      == '0000':
                print ("ignore some dir:"+file)
                continue 

            g_MyMovies.append(movie.Movie(DiskPath,file))
            if g_MyMovies[g_Count].CheckMovie() == 0:
                print ("CheckMovie error:"+g_MyMovies[g_Count].DirName)

            else:
                print ("CheckMovie correct:"+g_MyMovies[g_Count].DirName)                
            g_Count += 1
    return 1    

if __name__ == '__main__' :

    LogClear(DebugLogFile)
    LogClear(ExecLogFile)
    LogClear(ErrorLogFile)

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
    else :
        print ("too many argv:")
        exit()
        
    if Choise == "0" or Choise.lower() == "bt":
        g_CheckDiskPath = "/media/root/BT/movies" ; g_CheckDisk = "BT"
    elif Choise == "1" or Choise.lower() == "wd4t" :
        g_CheckDiskPath = "/media/root/wd4t" ; g_CheckDisk = "wd4t"
    elif Choise == "2" or Choise.lower() == "wd2t" :
        g_CheckDiskPath = "/media/root/wd2t" ; g_CheckDisk = "wd2t"
    elif Choise == "3" or Choise.lower() == "wd2t-2" :
        g_CheckDiskPath = "/media/root/wd2t-2" ; g_CheckDisk = "wd2t-2"
    elif Choise == "4" or Choise.lower() == "sg3t" :
        g_CheckDiskPath = "/media/root/sg3t" ; g_CheckDisk = "sg3t"
    elif Choise == "5" or Choise.lower() == "sg3t-2" :
        g_CheckDiskPath = "/media/root/sg3t-2" ; g_CheckDisk = "sg3t-2"
    elif Choise == "6" or Choise.lower() == "sg8t" :
        g_CheckDiskPath = "/media/root/SG8T" ; g_CheckDisk = "sg8t"
    else :
        g_CheckDiskPath = Choise ; g_CheckDisk = ""
        print ("your choise is :"+Choise)

    movie.Movie.ErrorLogFile  =  ErrorLogFile
    movie.Movie.ExecLogFile  =  ExecLogFile
    movie.Movie.DebugLogFile  =  DebugLogFile
    movie.Movie.ToBeExecDirName  =  ToBeExecDirName
    movie.Movie.ToBeExecRmdir  =  ToBeExecRmdir
    
    print ("begin check movie"+g_CheckDiskPath)
    g_MyMovies = []; g_Count = 0
    CheckDiskMovie(g_CheckDiskPath)
    print ("end check movie"+g_CheckDiskPath)    
        

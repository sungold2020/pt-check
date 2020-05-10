#!/usr/bin/python3
# coding=utf-8
import os
import os.path
import shutil
import re
import datetime
import time
import random
from gen import Gen
#日志文件
DebugLogFile = "log/douban.log"             #日志，可以是相对路径，也可以是绝对路径
ErrorLogFile = "log/douban.err"             #错误日志
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
    print(Str)
    Log(DebugLogFile,Str)
    if Mode == "p": print(Str)
    
def ErrorLog(Str):
    print(Str)
    DebugLog(Str)
    Log(ErrorLogFile,Str)
################################################################################   

import mysql.connector
mydb = mysql.connector.connect(
  host="localhost",      # 数据库主机地址
  user="dummy",    # 数据库用户名
  passwd="" ,  # 数据库密码
  database="db_movies"
)
mycursor = mydb.cursor()

select_sql = "select Nation, Year, DoubanID, IMDBID, Name, ForeignName, Director, Actors, Episodes, Poster, Number, Copy from movies where director = '' order by number"
mycursor.execute(select_sql)
result = mycursor.fetchall()
for tSelect in result:
    dbNation      = tSelect[0]
    dbYear        = tSelect[1]
    dbDoubanID    = tSelect[2]
    dbIMDBID      = tSelect[3]
    dbName        = tSelect[4]
    dbForeignName = tSelect[5]
    dbDirector    = tSelect[6]
    dbActors      = tSelect[7]
    dbEpisodes    = tSelect[8]
    dbPoster      = tSelect[9]
    dbNumber      = tSelect[10]
    dbCopy        = tSelect[11]
    dbNumberName    = str(dbNumber).zfill(4)+"-"+dbName
    
    print("{}:{} :: {}".format(dbNumberName,dbDirector,dbActors))
    tDirector = input("Director：")
    print(tDirector)
    if tDirector != '': dbDirector = tDirector
    
    tActors = input("Acotrs：")
    print(tActors)
    if tActors != '': dbActors = tActors
    
    print("{} :: {}".format(dbDirector,dbActors))
   
    up_sql = 'update movies set \
              DoubanID=%s,IMDBID=%s,ForeignName=%s,Director=%s,Actors=%s,Episodes=%s,Poster=%s where Number=%s and Copy=%s'
    up_val=(dbDoubanID, dbIMDBID, dbForeignName, dbDirector, dbActors, dbEpisodes, dbPoster,    dbNumber,  dbCopy)     
    try:
        mycursor.execute(up_sql,up_val)
        mydb.commit()
    except Exception as err:
        print(err)
        ErrorLog("update error:"+dbNumberName+":"+up_sql)
        break
    else:
        DebugLog("success update table:"+dbNumberName)


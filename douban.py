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

select_sql = "select Nation, Year, DoubanID, IMDBID, Name, ForeignName, Director, Actors, Episodes, Poster, Number, Copy from movies"
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

    #如果director非空，说明已经刮削过。否则开始刮削
    if dbDirector != "" : DebugLog("igore :"+dbNumberName);continue
    
    Link = ""
    if dbDoubanID != "" : Link = {'site':'douban','sid':dbDoubanID}
    elif dbIMDBID != "" : Link = {'site':'douban','sid':dbIMDBID}
    else : ErrorLog("empty link:"+dbNumberName);  continue
    
    tSeconds = random.randint(60,500)
    DebugLog("sleep {} Seconds:".format(tSeconds))
    time.sleep(tSeconds)
    DebugLog("begin :"+dbNumberName)
    try:
        tMovieInfo = Gen(Link).gen(_debug=True)     
    except Exception as err:
        print(err)
        ErrorLog("failed to gen:"+dbNumberName)
        continue

    if not tMovieInfo["success"]:
        print(tMovieInfo["error"])
        ErrorLog("failed to request from douban:"+dbNumberName)
        continue

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
    try:  tIMDBScore   = tMovieInfo['imdb_rating']
    except : tIMDBScore = ""
    tOtherNames  = ','.join(tMovieInfo['aka'])
        
    if   tNation[-1:] == '国' : tNation = tNation[:-1]  #去除国家最后的国字
    elif tNation == '香港'    : tNation = '港'
    elif tNation == '中国大陆': tNation = '国'
    elif tNation == '中国台湾': tNation = '台'
    elif tNation == '日本'    : tNation = '日'
    else : pass
    tIndex = tIMDBScore.find('/')
    if tIndex > 0: tIMDBScore = tIMDBScore[:tIndex]
    else:          tIMDBScore = ""
        
    if tNation != dbNation   : ErrorLog( 'diff Nation: ({}::{}) ::{}'.format(dbNation,tNation,dbNumberName) )
    if tYear   != dbYear     : ErrorLog( 'diff Year  : ({}::{}) ::{}'.format(dbYear,tYear,dbNumberName) )
    if dbName.find(tName)<0  : ErrorLog( 'diff Name  : ({}::{}) ::{}'.format(dbName,tName,dbNumberName) )

    dbDoubanID    = tDoubanID
    dbIMDBID      = tIMDBID
    dbForeignName = tForeignName
    dbDirector    = tDirector
    dbActors      = tActors
    dbEpisodes    = tEpisodes
    dbPoster      = tPoster
    dbDoubanScore = tDoubanScore
    dbIMDBScore   = tIMDBScore
    dbOtherNames  = tOtherNames
    DebugLog("DoubanID:{}".format(dbDoubanID))
    DebugLog("IMDBID:{}".format(dbIMDBID))
    DebugLog("ForeignName:{}".format(dbForeignName))
    DebugLog("Director:{}".format(dbDirector))
    DebugLog("Actors:{}".format(dbActors))
    DebugLog("Episodes:{}".format(dbEpisodes))
    DebugLog("Poster:{}".format(dbPoster))
    DebugLog("DoubanScore:{}".format(dbDoubanScore))
    DebugLog("IMDBScore:{}".format(dbIMDBScore))
    DebugLog("OtherNames:{}".format(dbOtherNames))
    
    up_sql = 'update movies set \
              DoubanID=%s,IMDBID=%s,ForeignName=%s,Director=%s,Actors=%s,Episodes=%s,Poster=%s,DoubanScore=%s,IMDBScore=%s,OtherNames=%s where Number=%s and Copy=%s'
    up_val=(dbDoubanID, dbIMDBID, dbForeignName, dbDirector, dbActors, dbEpisodes, dbPoster, dbDoubanScore, dbIMDBScore, dbOtherNames,       dbNumber,  dbCopy)     
    try:
        mycursor.execute(up_sql,up_val)
        mydb.commit()
    except Exception as err:
        print(err)
        ErrorLog("update error:"+dbNumberName+":"+up_sql)
        break
    else:
        DebugLog("success update table:"+dbNumberName)


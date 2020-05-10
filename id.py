#!/usr/bin/python3
# coding=utf-8
import mysql.connector

#手工设置imdbid的脚本

DBUserName = 'dummy'
DBPassword = ''
DBName     = 'db_movies'

g_DB = mysql.connector.connect(host="localhost", user=DBUserName, passwd=DBPassword, database=DBName)
g_MyCursor = g_DB.cursor()
se_sql = 'select RSSName,ID,Title from rss where imdbid="" and doubanid="" and downloaded=1'
try:
    g_MyCursor.execute(se_sql)
    tSelectResult = g_MyCursor.fetchall()
except Exception as err: 
    print(err)
    exit()
 
for tSelect in tSelectResult:
    RSSName = tSelect[0]
    ID      = tSelect[1]
    Title   = tSelect[2]
    tInput=input(Title+":")
    print(tInput)
    if tInput == "": continue
    
    if tInput[:2] == 'tt':
        IMDBID = tInput
        DoubanID = ""
    else:
        DoubanID = tInput
        IMDBID   = ""

    update_sql = "UPDATE rss set DoubanID=%s,IMDBID=%s where RSSName=%s and ID=%s"
    update_val = (DoubanID,IMDBID,RSSName,ID)
    try:
        g_MyCursor.execute(update_sql,update_val)
        g_DB.commit()
    except Exception as err:
        print(err)
        exit()
        

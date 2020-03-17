#!/usr/bin/python3
# coding=utf-8
import qbittorrentapi
if __name__ == '__main__' :
    qbt_client = qbittorrentapi.Client(host='localhost:8989', username='admin', password='adminadmin')
    try:
        qbt_client.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        ErrorLog("Failed to Connect QB:")
        exit() 
    for torrent in qbt_client.torrents_info():       
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
        else:
            if Tags != 'other':
                torrent.remove_tags()
                torrent.add_tags('other')
                
        

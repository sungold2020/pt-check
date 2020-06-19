#!/usr/bin/python3
import bs4
import requests
import os
import lxml
import re
import datetime

class NexusPage():
    '''
    Getting a torrent page with all torrents in it
    '''
    site_name = "Mteam"
    site_cookie = ""
    site_url = "https://pt.m-team.cc/movie.php"
    #site_name = "JoyHD"
    #site_url = "https://www.joyhd.net/torrents.php"
    #site_cookie = "PHPSESSID=1b4ngj5fbahu34998vc6jqcl93; t-se=1; login-se=1; c_secure_uid=MTgzOTQ%3D; c_secure_pass=1e9bf921616e2c4680cb2bf8950ccf69; c_secure_ssl=eWVhaA%3D%3D; c_secure_tracker_ssl=eWVhaA%3D%3D; c_secure_login=bm9wZQ%3D%3D"

    user_agent = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Safari/605.1.15 Epiphany/605.1.15"

    free_tag = 'pro_free'
    free_tag2 = 'pro_free2up'

    torrents_class_name = '.torrentname'

    FreeDebugFile = "log/free.debug"

    def __init__(self):
        self.processed_list = []
        #self.torrents_class_name = torrents_class_name
        
        # Using Session to keep cookie
        cookie_dict = {"cookie":NexusPage.site_cookie}
        s = requests.Session()
        s.cookies.update(cookie_dict)
    
        try:
            if NexusPage.user_agent: 
                res = s.get(NexusPage.site_url, headers={'User-Agent':NexusPage.user_agent})
            else:
                res = s.get(NexusPage.site_url)
        except Exception as err:
            print(err)
            self.Print("failed to request from "+NexusPage.site_name)
        self.soup = bs4.BeautifulSoup(res.text,'lxml')
        self.processed_list = self.soup.select(NexusPage.torrents_class_name)

    def find_free(self):
        pattern = r'id=(\d+)'
        free_state = []
        # Check free and add states
        for entry in self.processed_list:            
            details = entry.a['href']
            torrent_id = re.search(pattern, details).group(1)
            title = entry.get_text()
            
            #if torrent is free:
            if entry.find(class_=NexusPage.free_tag) or entry.find(class_=NexusPage.free_tag2):
                last_download_url = 'NULL'
                # Find the tag that download url in
                for subentry in entry.select('.embedded'):
                    if 'href="download.php?' in str(subentry):
                        last_download_url = subentry.a['href']
                free_state.append((True , torrent_id, title, details, last_download_url))
            else:
                free_state.append((False, torrent_id, title, details, "NULL"))
        for free_torrent in free_state:
            self.Print("{} {} {} ".format(str(free_torrent[0]).ljust(5),free_torrent[1],free_torrent[2]))

        return free_state

    def Print(self,Str):
        fo = open(NexusPage.FreeDebugFile,"a+")
        tCurrentTime = datetime.datetime.now()
        fo.write(tCurrentTime.strftime('%Y-%m-%d %H:%M:%S')+"::")
        fo.write(Str+'\n')
        fo.close()



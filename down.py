#!/usr/bin/env python3

import re
from sys import argv
from pathlib import Path
from multiprocessing.pool import ThreadPool
from lxml import html
from lxml import etree as et
import requests


PR3_BASE_URL = "https://www.polskieradio.pl"

def getContent(base_url, page_number = 1):
    ses = requests.Session()
    base_req = ses.get(base_url)
    tree = html.fromstring(base_req.text)
    pages = tree.xpath("//div[starts-with(@id,'ctl00_pager')]")[0]
    last_page_html = pages.xpath("./ul/li")[-1:][0]
    last_page = last_page_html.xpath("./a//text()")[0].strip()
    print("Pages:", last_page)
    for page_no in range(int(page_number), int(last_page) + 1):
        files_2_download = []
        list_page_url = base_url + "/Strona/" + str(page_no)
        page_body = ses.get(list_page_url)
        paget_html = html.fromstring(page_body.text)
        articles = paget_html.xpath("/html/body/div[2]/form/div[1]/div[1]/div[3]/div[1]/div[2]/div[2]/div/div[1]/div/section/article")
        print("  Page", page_no, "of", last_page, "(", len(articles), "files )")
        for article in articles:
            article_title = article.xpath(".//a/@title")[0].replace(" ", "_").replace(".","").replace(":","-")
            article_link = article.xpath(".//a/@href")[0]
            article_body = ses.get(PR3_BASE_URL + article_link)
            article_html = html.fromstring(article_body.text)
            try:
                mp3_mess = article_html.xpath("//aside[@id = 'box-sounds']//text()")[1]
            except:
                print("    Can't find mp3 for", article_title, "so skipping")
                continue
            regex = re.compile(r"\/\/static\.prsa\.pl/.+\.mp3")
            matchObj = regex.search(mp3_mess).group(0)
            files_2_download.append({ "url": "https:" + matchObj, "file": article_title + ".mp3"})
        ThreadPool(2).map(download, files_2_download)



def download(pr3_object):
    article_file = Path(pr3_object["file"])
    if article_file.is_file():
        print("   ", pr3_object["file"], "exists so skipping" )
        return
    print("    Downloading " + pr3_object["file"])
    r = requests.get(pr3_object["url"], allow_redirects=True)
    open(pr3_object["file"], 'wb').write(r.content)
    return

def printHelp():
    print("Zaciagacz audycji PR3\n\n" +
    argv[0] + " link_do_audycji [numer_strony_poczatkowej=1]\n\n" 
    "na przyklad tak wyglada sciaganie audycji Aksamit od strony 5:\n" 
    + argv[0] + " https://www.polskieradio.pl/9/5360 5")

def main():
    if len(argv) == 2:
        getContent(argv[1])
    elif len(argv) == 3:
         getContent(argv[1], argv[2])
    else:
        printHelp()

main()
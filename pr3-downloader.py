#!/usr/bin/env python3

import os
import re
from sys import argv
import json
from pathlib import Path
from multiprocessing.pool import ThreadPool
from lxml import html
from lxml import etree as et
import requests

DEBUG = False
if "PR3_DEBUG" in os.environ:
    DEBUG = bool(os.environ["PR3_DEBUG"])
    print("DEBUG - verbose logging and not downloading, doing first element only")


PR3_BASE_URL = "https://www.polskieradio.pl"

def getContent(base_url, page_number=1):
    ses = requests.Session()
    base_req = ses.get(base_url)
    tree = html.fromstring(base_req.text)
    pages = tree.xpath("//div[starts-with(@id,'ctl00_pager')]")[0]
    last_page_html = pages.xpath("./ul/li")[-1:][0]
    last_page = last_page_html.xpath("./a//text()")[0].strip()
    tab_params = last_page_html.xpath("./a//@onclick")
    print("Pages:", last_page)

    for page_no in range(int(page_number), int(last_page) + 1):
        files_2_download = []
        if len(tab_params) == 1:
            articles = get_arts_from_tabs_content(ses, tab_params[0], page_no)
        else:
            articles = get_arts_from_pages(ses, base_url, page_no)

        print("  Page", page_no, "of", last_page,
              "(", len(articles), "files )")

        for article in articles:
            article_title = article.split(",")[-1:][0]
            article_body = ses.get(article)
            article_html = html.fromstring(article_body.text)
            try:
                mp3_mess = article_html.xpath(
                    "//aside[@id = 'box-sounds']//text()")[1]
                regex = re.compile(r"\/\/static\.prsa\.pl/.+\.mp3")
                file_url = regex.search(mp3_mess).group(0)
                file_full_url = "https:" + file_url
            except IndexError:
                try:
                    mp3_media = article_html.xpath(
                        "//a[@class = 'pr-media-play']//@data-media")[0]
                    file_full_url = "https:" + json.loads(mp3_media)['file']
                except IndexError:
                    print("    Can't find mp3 for",
                          article_title, "so skipping")
                    continue
            files_2_download.append(
                {"url": file_full_url, "file": article_title + ".mp3"})
            if DEBUG:
                break
        ThreadPool(1).map(download, files_2_download)
        if DEBUG:
            break

def get_articles_hrefs(html_text):
    articles_hrefs = html_text.xpath("./ul/li//a/@href")
    if not articles_hrefs:
        articles_hrefs = html_text.xpath("./section/article/a/@href")
    if DEBUG:
        print("DEBUG 1 article href", articles_hrefs[0])
    return articles_hrefs

def get_arts_from_pages(ses, base_url, page_number):
    list_page_url = base_url + "/Strona/" + str(page_number)
    page_get = ses.get(list_page_url)
    page_html = html.fromstring(page_get.text)
    articles_div = page_html.xpath(
        "//form/div[1]/div[1]/div[3]/div[1]/div[*]/div[2]/div/div[1]/div")[0]
    return list(map(lambda art: PR3_BASE_URL + art, get_articles_hrefs(articles_div)))


def get_arts_from_tabs_content(ses, tab_options, page_number):
    regex = re.compile("\((.+)\)")
    matchObjs = regex.search(tab_options).group(1).split(',')
    objs = list(map(lambda match_obj: match_obj.strip(), matchObjs))

    params = {"boxInstanceId": int(objs[0]), "tabId": int(objs[1]), "sectionId": int(objs[3]), "categoryId": int(objs[4]),
              "categoryType": int(objs[5]), "subjectIds": objs[6], "tagIndexId": int(objs[7]),
              "queryString": "stid=" + objs[3] + "&ctid=" + objs[4],
              "name": objs[9], "pageNumber": int(page_number),
              "pagerMode": 0, "openArticlesInParentTemplate": False,
              "idSectionFromUrl": int(objs[11]), "maxDocumentAge": int(objs[12]), "showCategoryForArticle": False}
    page_with_tabs = ses.post(PR3_BASE_URL +
                              "/CMS/TemplateBoxesManagement/TemplateBoxTabContent.aspx/GetTabContent",
                              json=params)#, headers=headers)
    content_html = html.fromstring(
        json.loads(page_with_tabs.text)['d']['Content'])
    articles_url = list(map(lambda art: PR3_BASE_URL + art, get_articles_hrefs(content_html)))
    if DEBUG:
        print("DEBUG 1 article url:", articles_url[0])
    return articles_url


def download(pr3_object):
    article_file = Path(pr3_object["file"])
    if article_file.is_file():
        print("   ", pr3_object["file"], "exists so skipping")
        return
    print("    Downloading " + pr3_object["file"], end='')
    if DEBUG:
        print(" DEBUG: " + pr3_object["url"])
        return
    else:
        print("")
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

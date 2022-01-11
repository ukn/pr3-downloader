#!/usr/bin/env python3

import os
import re
from sys import argv, stderr
import json
from pathlib import Path
from functools import reduce
from multiprocessing.pool import ThreadPool
from lxml import html
import requests

DEBUG = False
if "PR3_DEBUG" in os.environ:
    DEBUG = bool(os.environ["PR3_DEBUG"])
    print("DEBUG - verbose logging and not downloading, doing first element only")

THREADPOOL = 1
if "THREADPOOL" in os.environ and int(os.environ["THREADPOOL"]) > 0:
    THREADPOOL = int(os.environ["THREADPOOL"])

PR3_BASE_URL = "https://www.polskieradio.pl"


def getContent(base_url, start_page=1, end_page=None):
    ses = requests.Session()
    base_req = ses.get(base_url)
    tree = html.fromstring(base_req.text)
    try:
        pages = tree.xpath("//div[starts-with(@id,'ctl00_pager')]")[0]
        last_page_html = pages.xpath("./ul/li")[-1:][0]
        last_page = last_page_html.xpath("./a//text()")[0].strip()
        if end_page is None:
            end_page = int(last_page)
        tab_params = last_page_html.xpath("./a//@onclick")
        print(
            f"Pages to process: {start_page} - {end_page} out of {last_page}")
        for page_no in range(int(start_page), int(end_page)+1):
            global STATE
            STATE = {}
            if len(tab_params) == 1:
                articles = get_arts_from_tabs_content(
                    ses, tab_params[0], page_no)
            else:
                articles = get_arts_from_pages(ses, base_url, page_no)
            print("  Page", page_no, "(", len(articles), "files )")
            files_2_download = parse_articles(ses, articles)

            ThreadPool(THREADPOOL).map(download, files_2_download)
            if DEBUG:
                break
    except IndexError:
        articleSoundsList = tree.xpath(
            "//div[@id = 'articleSoundsList']//ul/li")
        print(len(articleSoundsList), "files to download")
        files_2_download = parse_articles(ses, articleSoundsList)
        ThreadPool(THREADPOOL).map(download, files_2_download)


def parse_articles(ses, articles):
    files_for_download = []
    for article in articles:
        art_type = type(article).__name__
        if art_type == "str":
            article_title = article.split(",")[-1:][0]
            article_body = ses.get(article)
            article_html = html.fromstring(article_body.text)
        else:
            article_title_pre = article.xpath(
                "./div/a[@class = 'pr-media-play']/@data-media")[0]
            article_title = json.loads(article_title_pre)['desc']
            # print(article_title)
            article_html = article
        try:
            mp3_mess = article_html.xpath(
                "//aside[@id = 'box-sounds']//text()")[1]
            regex = re.compile(r"\/\/static\.prsa\.pl/.+\.mp3")
            file_url = regex.search(mp3_mess).group(0)
            file_full_url = "https:" + file_url
        except IndexError:
            try:
                mp3_media = article_html.xpath(
                    "./div/a[@class = 'pr-media-play']//@data-media")[0]
                file_full_url = "https:" + json.loads(mp3_media)['file']
            except IndexError:
                print("    Can't find mp3 for",
                      article_title, "so skipping")
                continue
        files_for_download.append(
            {"url": file_full_url, "file": article_title.lower() + ".mp3"})
        if DEBUG:
            return files_for_download
    return files_for_download


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
                              json=params)  # , headers=headers)
    content_html = html.fromstring(
        json.loads(page_with_tabs.text)['d']['Content'])
    articles_url = list(map(lambda art: PR3_BASE_URL + art,
                            get_articles_hrefs(content_html)))
    if DEBUG:
        print("DEBUG 1 article url:", articles_url[0])
    return articles_url


def download(file_object):
    columns = os.get_terminal_size().columns
    global STATE
    CLR = "\x1B[0K"
    filename = f'{file_object["file"]}'
    if Path(filename).is_file():
        print(f"    {filename} exists so skipping")
        return
    if DEBUG:
        print("[DEBUG] " + file_object["url"])
        return
    try:
        r = requests.get(file_object["url"], allow_redirects=True, stream=True)
        # Estimates the number of bar updates
        block_size = 1024 * 1024
        file_size = int(r.headers.get('Content-Length', None))
        # print(file_size)
        with open(filename + ".tmp", 'wb') as f:
            for i, chunk in enumerate(r.iter_content(chunk_size=1 * block_size)):
                if r.raise_for_status() or r.status_code != 200:
                    raise Exception("Downloading error!")
                f.write(chunk)
                STATE[filename] = f'{int(((i*len(chunk))/file_size)*100)}%'
                # display progress dynamically only if fits the terminal
                state_length = reduce(
                    lambda acc, file: acc + len(file) + len(STATE[file]), STATE, 10*THREADPOOL)
                if columns > state_length and i % 4 == 0:
                    print(f"{STATE}{CLR}", end="\r")
        STATE[filename] = '100%'
        os.rename(filename + ".tmp", filename)
    except Exception as e:
        print(f'Downloading stopped {filename}: {e}', file=stderr)
        if Path(filename).is_file():
            os.unlink(filename)
        return
    print(f"    {filename} downloaded{CLR}")
    STATE.pop(filename)


def printHelp():
    print("Zaciagacz audycji PR3\n\n" +
          argv[0] + " link_do_audycji [pierwsza_strona=1] [ostatnio_strona=10]\n\n"
          "na przyklad tak wyglada sciaganie audycji Aksamit od strony 5 do ostatniej:\n"
          + argv[0] + " https://www.polskieradio.pl/9/5360 5")


def main():
    try:
        if len(argv) == 2:
            getContent(argv[1])
        elif len(argv) == 3:
            getContent(argv[1], argv[2])
        elif len(argv) == 4:
            getContent(argv[1], argv[2], argv[3])
        else:
            printHelp()
    except KeyboardInterrupt:
        print("\nExiting...")
        exit()


main()

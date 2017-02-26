# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# pelisalacarta - XBMC Plugin
# Conector para flashx
# http://blog.tvalacarta.info/plugin-xbmc/pelisalacarta/
# ------------------------------------------------------------

import os
import re
import time
import urllib

from core import config
from core import logger
from core import jsunpack
from core import scrapertools


headers = [['User-Agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0'],
           ['Accept', '*/*'],
           ['Connection', 'keep-alive']]


def test_video_exists(page_url):
    logger.info("pelisalacarta.servers.flashx test_video_exists(page_url='%s')" % page_url)

    data = scrapertools.downloadpageWithoutCookies(page_url.replace("playvid-", ""))

    if 'File Not Found' in data:
        return False, "[FlashX] El archivo no existe o ha sido borrado"
    elif 'Video is processing now' in data:
        return False, "[FlashX] El archivo se está procesando"

    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    logger.info("pelisalacarta.servers.flashx url=" + page_url)

    # Lo pide una vez
    data = scrapertools.cache_page(page_url, headers=headers)
    # Si salta aviso, se carga la pagina de comprobacion y luego la inicial
    if "You try to access this video with Kodi" in data:
        url_reload = scrapertools.find_single_match(data, 'try to reload the page.*?href="([^"]+)"')
        url_reload = "http://www.flashx.tv" + url_reload[1:]
        try:
            data = scrapertools.cache_page(url_reload, headers=headers)
            data = scrapertools.cache_page(page_url, headers=headers)
        except:
            pass

    matches = scrapertools.find_multiple_matches(data, "<script type='text/javascript'>(.*?)</script>")
    for n,m in enumerate(matches):
        if m.startswith("eval"):
            try:
                m = jsunpack.unpack(m)
                fake = (scrapertools.find_single_match(m, "(\w{40,})") == "")
                if fake:
                    m = ""
                else:
                    break
            except:
                m = ""
    match = m

    if not "sources:[{file:" in match:
        page_url = page_url.replace("playvid-", "")
        data = scrapertools.downloadpageWithoutCookies(page_url)

        file_id = scrapertools.find_single_match(data, "'file_id', '([^']+)'")
        aff = scrapertools.find_single_match(data, "'aff', '([^']+)'")
        headers_c = [['User-Agent', 'Mozilla/5.0'],
                     ['Referer', page_url],
                     ['Cookie', '; lang=1']]
        coding_url = "https:"+scrapertools.find_single_match(data, '(?i)src="(?:https:|)((?://www.flashx.tv|//files.fx.fastcontentdelivery.com)/\w+.js\?[^"]+)"')
        if coding_url.endswith("="):
            coding_url += file_id
        coding = scrapertools.downloadpage(coding_url, headers=headers_c)

        data = scrapertools.downloadpage(page_url, headers=headers)
        flashx_id = scrapertools.find_single_match(data, 'name="id" value="([^"]+)"')
        fname = scrapertools.find_single_match(data, 'name="fname" value="([^"]+)"')
        hash_f = scrapertools.find_single_match(data, 'name="hash" value="([^"]+)"')
        post = 'op=download1&usr_login=&id=%s&fname=%s&referer=&hash=%s&imhuman=Proceed+to+video' % (flashx_id, urllib.quote(fname), hash_f)
        wait_time = scrapertools.find_single_match(data, "<span id='xxc2'>(\d+)")

        try:
           time.sleep(int(wait_time)+1)
        except:
           time.sleep(6)
        headers.append(['Referer', "https://www.flashx.tv/"])
        headers.append(['Cookie', 'lang=1; file_id=%s; aff=%s' % (file_id, aff)])
        data = scrapertools.downloadpage('https://www.flashx.tv/dl?playthis', post=post, headers=headers)

        matches = scrapertools.find_multiple_matches(data, "(eval\(function\(p,a,c,k.*?)\s+</script>")
        for match in matches:
            if match.startswith("eval"):
                try:
                    match = jsunpack.unpack(match)
                    fake = (scrapertools.find_single_match(match, "(\w{40,})") == "")
                    if fake:
                        match = ""
                    else:
                        break
                except:
                    match = ""

        if not match:
            match = data

    # Extrae la URL
    # {file:"http://f11-play.flashx.tv/luq4gfc7gxixexzw6v4lhz4xqslgqmqku7gxjf4bk43u4qvwzsadrjsozxoa/video1.mp4"}
    video_urls = []
    media_urls = scrapertools.find_multiple_matches(match, '\{file\:"([^"]+)",label:"([^"]+)"')
    subtitle = ""
    for media_url, label in media_urls:
        if media_url.endswith(".srt") and label == "Spanish":
            try:
                from core import filetools
                data = scrapertools.downloadpage(media_url)
                subtitle = os.path.join(config.get_data_path(), 'sub_flashx.srt')
                filetools.write(subtitle, data)
            except:
                import traceback
                logger.info("pelisalacarta.servers.flashx Error al descargar el subtítulo: "+traceback.format_exc())
            
    for media_url, label in media_urls:
        if not media_url.endswith("png") and not media_url.endswith(".srt"):
            video_urls.append(["." + media_url.rsplit('.', 1)[1] + " [flashx]", media_url, 0, subtitle])

    for video_url in video_urls:
        logger.info("pelisalacarta.servers.flashx %s - %s" % (video_url[0], video_url[1]))

    return video_urls


# Encuentra vídeos del servidor en el texto pasado
def find_videos(data):
    # Añade manualmente algunos erróneos para evitarlos
    encontrados = set()
    devuelve = []

    # http://flashx.tv/z3nnqbspjyne
    # http://www.flashx.tv/embed-li5ydvxhg514.html
    patronvideos = 'flashx.(?:tv|pw)/(?:embed.php\?c=|embed-|playvid-|)([A-z0-9]+)'
    logger.info("pelisalacarta.servers.flashx find_videos #" + patronvideos + "#")
    matches = re.compile(patronvideos, re.DOTALL).findall(data)

    for match in matches:
        titulo = "[flashx]"
        url = "https://www.flashx.tv/playvid-%s.html" % match
        if url not in encontrados:
            logger.info("  url=" + url)
            devuelve.append([titulo, url, 'flashx'])
            encontrados.add(url)
        else:
            logger.info("  url duplicada=" + url)

    return devuelve

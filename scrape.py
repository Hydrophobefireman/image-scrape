import json
import os
import re
import threading
import time
import requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup as bs
import html

BASEURL_GOOGLE = "https://www.google.com/search?q={query}&tbm=isch"
BASEURL_BING = "https://bing.com/images/search?q={query}"
basic_headers = {
    "Accept-Encoding": "gzip,deflate",
    "User-Agent": "Mozilla/5.0 (Windows; U; Windows NT 10.0; en-US) AppleWebKit/604.1.38 (KHTML, like Gecko) Chrome/68.0.3325.162",
    "Upgrade-Insecure-Requests": "1",
    "dnt": "1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
}
sess = requests.Session()
with open(".mimetypes") as f:
    __mimes__ = json.loads(f.read())


def get_data_bing(url, adl=False):
    bing_base_adlt_url = "https://bing.com/settings.aspx?pref_sbmt=1&adlt_set=off&adlt_confirm=1&is_child=0&"
    print("[Bing]Fetching:", url)
    page = sess.get(url, headers=basic_headers, allow_redirects=True)
    cookies = dict(page.cookies)
    data = []
    soup = bs(page.text, "html.parser")
    if adl:
        _ru = soup.find(attrs={"id": "ru"})
        _guid = soup.find(attrs={"id": "GUID"})
        print(page.url)
        if _ru is None or _guid is None:
            raise Exception("Could Not verify age")
        ru = _ru.attrs.get("value")
        guid = _guid.attrs.get("value")
        new_url = bing_base_adlt_url + urlencode({"ru": ru, "GUID": guid})
        req = sess.get(
            new_url, headers=basic_headers, cookies=cookies, allow_redirects=True
        )
        if "/images/" not in req.url:
            raise Exception("Could not Find Images")
        soup = bs(req.text, "html.parser")
        print("[Bing]Age-Verified")
    atags = soup.find_all(attrs={"class": "iusc"}) or soup.find_all(attrs={"m": True})
    for tag in atags:
        m = tag.attrs.get("m")
        if m:
            js_data = json.loads(html.unescape(m))
            url = js_data["murl"]
            print("[Bing]Found", url)
            data.append(url)
    data = list(set(data))
    thread = [threading.Thread(target=fetch, args=(url, "bing")) for url in data]
    for th in thread:
        th.start()
    for th in thread:
        th.join()
    print("[bing]Downloaded All Data")


def get_data_google(url):
    data = []
    print("[Google]Fetching URL")
    page = sess.get(url, headers=basic_headers, allow_redirects=True)
    page.raise_for_status
    soup = bs(page.text, "html.parser")
    divs = soup.find_all("div", attrs={"class": "rg_meta notranslate"})
    for div in divs:
        meta = json.loads(div.text)
        img = meta.get("ou")
        if img:
            print("[Google]Found:", img)
            data.append(img)
    if not os.path.isdir("downloaded-images"):
        os.mkdir("downloaded-images")
    if not os.path.isdir(os.path.join("downloaded-images", "google")):
        os.mkdir(os.path.join("downloaded-images", "google"))
    data = list(set(data))
    thread = [threading.Thread(target=fetch, args=(url, "google")) for url in data]
    for th in thread:
        th.start()
    for th in thread:
        th.join()
    print("[Google]Downloaded All Data")


def fetch(url, directory):
    filename = re.sub(r"[^\w]", "-", url.split("/")[-1][:20])
    if not os.path.isdir(os.path.join("downloaded-images", directory)):
        os.mkdir(os.path.join("downloaded-images", directory))
    if os.path.isfile(os.path.join("downloaded-images", directory, filename)):
        filename = filename + str(int(time.time()))
    a = sess.get(url, stream=True, headers=basic_headers, allow_redirects=True)
    mime = __mimes__.get(a.headers.get("Content-Type", ""), "bin")
    with open(os.path.join("downloaded-images", directory, filename + mime), "wb") as f:
        for chunk in a.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)
    print("[%s]Downloaded:" % (directory), url)


if __name__ == "__main__":
    query = input("Enter Query:")
    adl = not 0
    get_data_bing(BASEURL_BING.format(query=query), adl=adl)
    get_data_google(BASEURL_GOOGLE.format(query=query))

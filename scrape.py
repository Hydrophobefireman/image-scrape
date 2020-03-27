import json
import os
import re
import threading
import time
import requests
from urllib.parse import urlencode, quote_plus
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


def _onlyId(soup):
    return list(
        filter(
            lambda x: "refinements" not in x.lower(),
            map(
                lambda x: x.attrs.get("data-id"),
                soup.find_all("div", attrs={"data-id": True}),
            ),
        )
    )


def bing_images(query, adult=True):
    bing_base_adlt_url = "https://bing.com/settings.aspx?pref_sbmt=1&adlt_set=off&adlt_confirm=1&is_child=0&"
    data, _urls = [], []
    results = {}
    results["query"] = query
    sess = requests.Session()
    url = "https://bing.com/images/search?q={q}".format(q=quote_plus(query))
    page = sess.get(url, headers=basic_headers, allow_redirects=True)
    soup = bs(page.text, "html.parser")
    if adult:
        _ru = soup.find(attrs={"id": "ru"})
        _guid = soup.find(attrs={"id": "GUID"})
        if _ru is None or _guid is None:
            raise Exception("Could Not verify age")
        ru = _ru.attrs.get("value")
        guid = _guid.attrs.get("value")
        new_url = bing_base_adlt_url + urlencode({"ru": ru, "GUID": guid})
        req = sess.get(new_url, headers=basic_headers, allow_redirects=True)
        if "/images/" not in req.url:
            raise Exception("Could not Find Images")
        soup = bs(req.text, "html.parser")
    atags = soup.find_all(attrs={"class": "iusc"}) or soup.find_all(attrs={"m": True})
    for tag in atags:
        m = tag.attrs.get("m")
        if m:
            js_data = json.loads(html.unescape(m))
            if not js_data.get("murl"):
                continue
            img = js_data["murl"]
            if img not in str(data):
                data.append(img)
    return data


def google_images(query, pages=1, page_start=0):
    """
    Google Image Searches,on average one page returns 100 results
    It also returns a fallback useful when the original image link dies
    """
    if pages * 100 >= 900 or page_start >= 1000:
        raise ValueError(
            "Google does not show more than (usually)900 responses for a query"
        )
    data, _urls, start = [], [], 0
    results = {}
    results["query"] = query
    sess = requests.Session()
    if not page_start:
        for j in range(pages):
            i = j + 1
            if i == 1:
                google_base = "https://www.google.com/search?q={q}&oq={q}&ie=UTF-8&tbm=isch".format(
                    q=quote_plus(query)
                )
            else:
                start += 100
                google_base = "https://www.google.com/search?q={q}&oq={q}&ie=UTF-8&start={start}&tbm=isch".format(
                    q=quote_plus(query), start=start
                )
            _urls.append(google_base)
    else:
        google_base = "https://www.google.com/search?q={q}&oq={q}&ie=UTF-8&start={start}&tbm=isch".format(
            q=quote_plus(query), start=page_start
        )
        _urls.append(google_base)
    results["urls"] = _urls
    for url in _urls:
        page = sess.get(url, headers=basic_headers, allow_redirects=True)
        txt = page.text
        soup = bs(txt, "html.parser")
        reg = r"""(?<=_defd\('defd).*?(?='\);)"""
        additional_defs = bs(
            "\n".join(
                list(
                    map(
                        lambda x: x.split("'")[-1]
                        .encode()
                        .decode("unicode_escape")
                        .replace("\\", ""),
                        re.findall(reg, txt),
                    )
                )
            ),
            "html.parser",
        )
        required_ids = [*_onlyId(soup)[1:], *_onlyId(additional_defs)]
        json_data_reg = r"""(?<=function\(\)\{return)(.*?)(?=\}\}\)\;)"""
        json_data = json.loads(
            re.search(json_data_reg, soup.find_all("script")[-2].text, re.DOTALL)
            .group()
            .strip()
        )[31][0][12][
            2
        ]  # yeah....
        for element in map(lambda x: x[1], json_data):
            if not element:
                continue
            if element[1] in required_ids:
                try:
                    img = element[3][0]
                    data.append(img)
                except:
                    continue
    return data


def get_data_bing(url, adl=False):
    data = set(bing_images(url, adl))
    thread = [threading.Thread(target=fetch, args=(url, "bing")) for url in data]
    for th in thread:
        th.start()
    for th in thread:
        th.join()
    print("[bing]Downloaded All Data")


def get_data_google(url):
    data = set(google_images(url))
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
    if not os.path.isdir("downloaded-images"):
        os.mkdir("downloaded-images")
    adl = not 0
    get_data_bing(BASEURL_BING.format(query=query), adl=adl)
    get_data_google(BASEURL_GOOGLE.format(query=query))

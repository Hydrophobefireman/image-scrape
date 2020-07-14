import os
import requests
from bs4 import BeautifulSoup as bs
import json
import re
from urllib.parse import quote_plus, urlencode, urlparse
import html
from warnings import warn
import threading
import time

_useragent = "Mozilla/5.0 (Windows; U; Windows NT 10.0; en-US) AppleWebKit/604.1.38 (KHTML, like Gecko) Chrome/68.0.3325.162"
basic_headers = {
    "Accept-Encoding": "gzip,deflate",
    "User-Agent": _useragent,
    "Upgrade-Insecure-Requests": "1",
    "dnt": "1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
}


class ExtractorError(BaseException):
    pass


save_dir = "images"

sess = requests.Session()
__mimes__ = {}
with open(".mimetypes") as f:
    __mimes__ = json.load(f)


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


json_data_reg = r"AF_initDataCallback\({.*?data:(\[.+\])(?=.?}\);)"


def search_regex(x):
    ret = re.search(json_data_reg, x.text, re.DOTALL)
    return json.loads(ret.groups()[0]) if ret else None


class Api(object):
    """main class for all searches"""

    def bing_images(self, query, adult=True):
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
        atags = soup.find_all(attrs={"class": "iusc"}) or soup.find_all(
            attrs={"m": True}
        )
        for tag in atags:
            m = tag.attrs.get("m")
            if m:
                js_data = json.loads(html.unescape(m))
                if not js_data.get("murl"):
                    continue
                img = js_data["murl"]
                link = js_data.get("purl")
                fallback = js_data.get("turl")
                title = link
                if img not in str(data):
                    data.append(
                        {"img": img, "link": link, "title": title, "fallback": fallback}
                    )
        results["data"] = data
        return results

    def google_images(self, query, pages=1, page_start=0, debug=False):
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
            if debug:
                return txt
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
            try:
                json_data = list(
                    filter(bool, (search_regex(x) for x in soup.find_all("script")))
                )[-1][31][0][12][
                    2
                ]  # yeah....
                for element in map(lambda x: x[1], json_data):
                    if not element:
                        continue
                    if element[1] in required_ids:
                        try:
                            data.append(
                                {
                                    "fallback": element[2][0],
                                    "img": element[3][0],
                                    "title": element[9]["2003"][3],
                                    "link": element[9]["2003"][2],
                                }
                            )
                        except:
                            continue
            except:
                pass
        results["data"] = data
        return results


_api = Api()


def google_images(*args, **kwargs):
    return _api.google_images(*args, **kwargs)["data"]


def bing_images(*args, **kwargs):
    return _api.bing_images(*args, **kwargs)["data"]


def get_data_bing(query, adl=True):
    data = set([x["img"] for x in bing_images(query, adl)])
    thread = [threading.Thread(target=fetch, args=(url, "bing")) for url in data]
    for th in thread:
        th.start()
    for th in thread:
        th.join()
    print("[bing]Downloaded All Data")


def get_data_google(query):
    data = set([x["img"] for x in google_images(query)])
    thread = [threading.Thread(target=fetch, args=(url, "google")) for url in data]
    for th in thread:
        th.start()
    for th in thread:
        th.join()
    print("[Google]Downloaded All Data")


def fetch(url, directory):
    filename = re.sub(r"[^\w]", "-", url.split("/")[-1][:20])
    try:
        os.mkdir(os.path.join(save_dir, directory))
    except:
        pass
    if os.path.isfile(os.path.join(save_dir, directory, filename)):
        filename = filename + str(int(time.time()))
    a = sess.get(url, stream=True, headers=basic_headers, allow_redirects=True)
    mime = __mimes__.get(a.headers.get("Content-Type", ""), "bin")
    with open(os.path.join(save_dir, directory, filename + mime), "wb") as f:
        for chunk in a.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)
    print("[%s]Downloaded:" % (directory), url)


if __name__ == "__main__":
    query = input("Enter Query:")
    if not os.path.isdir(save_dir):
        os.mkdir(save_dir)

    get_data_bing(query)
    get_data_google(query)

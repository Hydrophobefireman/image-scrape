import json
import os
import re
import threading
import secrets
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup as bs

basic_headers = {
    "Accept-Encoding": "gzip,deflate",
    "User-Agent": "Mozilla/5.0 (Windows; U; Windows NT 10.0; en-US) AppleWebKit/604.1.38 (KHTML, like Gecko) Chrome/68.0.3325.162",
    "Upgrade-Insecure-Requests": "1",
    "dnt": "1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
}
with open(".mimetypes") as f:
    __mimes__ = json.loads(f.read())

if not os.path.isdir("images"):
    os.mkdir("images")
directory = "images"


def fetch(u):
    og, fb = u["og"], u["fb"]

    sess = requests.Session()
    print("URL:", og)
    filename = secrets.token_urlsafe(10)
    if not os.path.isdir(directory):
        os.mkdir(directory)
    if os.path.isfile(os.path.join("downloaded-images", directory, filename)):
        filename = filename + secrets.token_urlsafe(5)
    try:
        a = sess.get(og, stream=True, headers=basic_headers, allow_redirects=True)
    except:
        sess.close()
        print(f"Using Fallback for {filename}")
        a = sess.get(fb, stream=True, headers=basic_headers, allow_redirects=True)
    mime = __mimes__.get(a.headers.get("Content-Type"))
    if not mime or mime == ".webp":
        print("BAD IMAGE")
        return
    with open(
        os.path.join("downloaded-images", directory, f"img{filename}" + mime), "wb"
    ) as f:
        for chunk in a.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)
    print("[%s]Downloaded:" % (directory), og)


def slideshow(loc):
    os.chdir(loc)
    os.system("""cat *| ffmpeg -r 1/3 -c:v libx264 -r 30 -pix_fmt yuv420p output.mkv""")


def get(term):
    url = f"https://searchpy.herokuapp.com/images/search?q={quote(term)}"
    print("URL:", url)
    soup = bs(requests.get(url, headers={"SearchPy-Custom": "1"}).text, "html5lib")
    imgs = []
    for x in soup.find_all("img"):
        imgs.append(
            {"og": x.attrs.get("data-original"), "fb": x.attrs.get("data-fallback")}
        )
    print("Number Of URLS:", len(imgs))
    thread = [threading.Thread(target=fetch, args=(url,)) for url in imgs]
    for t in thread:
        t.start()
    for t in thread:
        t.join()
    print("Making SlideShow")
    slideshow(directory)


if __name__ == "__main__":
    get(input("search:"))

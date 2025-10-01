import requests
from requests.exceptions import ReadTimeout, RequestException
from bs4 import BeautifulSoup
import trafilatura
from urllib.parse import urlparse, parse_qs, unquote
import time


# TODO list 
# 1. implement storage maangement (uodatiing storage with relevant info from the web)
# 2. 


def search_duckduckgo(query):
    url = f"https://duckduckgo.com/html/?q={query}"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    for a in soup.select(".result__a")[:5]:
        raw_url = a["href"]

        if "uddg=" in raw_url:
            parsed = urlparse(raw_url)
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                links.append(unquote(qs["uddg"][0]))
        else:
            if raw_url.startswith("//"):
                raw_url = "https:" + raw_url
            links.append(raw_url)
    print(f"{len(links)=}")
    return links

def extract_text(url):
    try:
        res = requests.get(                     # FIXME firewall error (use verify=False and request something like "столица сша")
            url, timeout=3, verify=False,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        res.raise_for_status()
        text = trafilatura.extract(res.text)
        return text
    except ReadTimeout as e:
        print(f"timeout while accessing to {url}")
    except RequestException as e:
        print(f"error {e} while accessing to {url}")
    return None

def parse_info(question):
    links = search_duckduckgo(question)
    # print("found links:")                                   # logs
    # for l in links:
    #     print(l)
    texts = [extract_text(link) for link in links]
    print("extracted")
    filtered_texts = [t for t in texts if t]
    output = "\n".join(filtered_texts)
    return output


if __name__ == "__main__":

    output = parse_info("столица сша")
    print(output)
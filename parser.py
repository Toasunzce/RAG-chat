import requests
from requests.exceptions import ReadTimeout, RequestException
from bs4 import BeautifulSoup
import trafilatura
from urllib.parse import urlparse, parse_qs, unquote
import time
import logging


# ================== CONFIG ==================


logger = logging.getLogger(__name__)


# ================== FUNCTIONS ===============


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
        logger.info(f"{time.ctime()}: timeout while accessing to {url}")                # logs
    except RequestException as e:
        logger.info(f"{time.ctime()}: error {e} while accessing to {url}")              # logs
    return None

def parse_info(question):
    links = search_duckduckgo(question)
    logger.info(f"{time.ctime()}: found links:")                                        # logs
    logger.info(f"{time.ctime()}: {links}")                                             # logs
    texts = [extract_text(link) for link in links]
    logger.info(f"{time.ctime()}: succesfully extracted")                               # logs
    filtered_texts = [t for t in texts if t]
    output = "\n".join(filtered_texts)
    return output


if __name__ == "__main__":
    logging.basicConfig(
        filename='logs/parser.log',
        level=logging.INFO,
        encoding='utf-8',
        filemode='w'
    )

    start_time = time.time()

    question = "столица сша"
    logger.info(f"{time.ctime()}: started")                                             # logs
    logger.info(f"{time.ctime()}: {question=}")                                         # logs
    output = parse_info(question)

    end_time = time.time()
    logger.info(f"execution time: {round(end_time - start_time, 2)}")
    print(output)
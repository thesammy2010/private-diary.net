import datetime
import json
import os
import bs4
from bs4 import Tag

from selenium import webdriver
from urllib.parse import urlparse, ParseResult, parse_qs

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
import time
import random
import requests

from config import COOKIES, PASSWORD, USERNAME

from typing import Any, List, Dict, Optional

from selenium.webdriver.remote.webelement import WebElement

URL: str = "http://privatediary.net/"


def sleep() -> None:
    t: float = random.randrange(0, 20) / 10
    time.sleep(t)


def login_with_cookies(driver: webdriver.Safari) -> bool:

    for cookie in COOKIES:
        driver.add_cookie(cookie)

    driver.get(URL)
    log_off: WebElement = driver.find_element(by=By.XPATH, value="/html/body/div[4]/div/div[2]/form/ul/li[2]/a")
    logged_in: bool = "Log off" in log_off.text
    if logged_in:
        print("Logged in with cookies")

    return logged_in


def login_with_password(driver: webdriver.Safari) -> None:
    driver.get(URL)
    driver.implicitly_wait(10)

    username: WebElement = driver.find_element(by=By.NAME, value="UserName")
    username.send_keys(USERNAME)
    sleep()

    password: WebElement = driver.find_element(by=By.NAME, value="Password")
    password.send_keys(PASSWORD)
    sleep()

    submit: WebElement = driver.find_element(by=By.CLASS_NAME, value="btn-primary")
    submit.click()
    sleep()


def get_number_of_pages(driver: webdriver.Safari) -> int:

    last_page: WebElement = driver.find_element(by=By.CLASS_NAME, value="PagedList-skipToLast")
    page_link: WebElement = last_page.find_element(by=By.XPATH, value=".//a")
    self_link: str = page_link.get_attribute("href")
    if not self_link:
        raise ValueError("No page element")

    url: ParseResult = urlparse(self_link)
    params: Dict[str, List[str]] = parse_qs(url.query)
    page: List[str] = params.get("page", [])

    if len(page) == 1:
        return int(page[0])


def get_entries(driver: webdriver.Safari, pages: int) -> List[str]:

    diary_entries: List[str] = []
    for page in range(pages):
        page_num: int = page + 1
        print(f"page={page_num}")

        driver.get(URL + f"?page={page_num}")
        entries: List[WebElement] = driver.find_elements(by=By.CLASS_NAME, value="btn-entry")
        for entry in entries:
            entry = entry.find_element(by=By.XPATH, value=".//a")
            link: str = entry.get_attribute("href")
            print(f"page={page_num}, link={link}")
            url: ParseResult = urlparse(link)
            entry_id: str = url.path.split("/")[-1]
            diary_entries.append(entry_id)

        sleep()

    return diary_entries


def build_entry_json(driver: webdriver.Safari, entry_id: str) -> None:

    print(entry_id)
    path: str = f"entries/{entry_id}"
    url: str = f"{URL}Records/Details/{entry_id}"
    os.makedirs(path, exist_ok=True)
    obj: Dict[str, Any] = {
        "metadata": {
            "id": entry_id,
            "url": url,
            "accessed_at": datetime.datetime.now().isoformat(),
            "path": path
        }
    }

    # fetch page
    driver.get(url)
    obj["title"] = get_title_from_page(driver=driver, path=path)
    obj["category"] = get_category_from_page(driver=driver)
    obj["date"] = get_date_from_page(driver=driver)
    obj["content"] = get_content_from_page(driver=driver, path=path)
    obj["assets"] = get_assets_from_page(driver=driver, path=path)

    with open(file=f"{path}/manifest.json", mode="w") as file:
        json.dump(obj, file, indent=4)


def get_title_from_page(driver: webdriver.Safari, path: str) ->str:
    title: WebElement = driver.find_element(by=By.XPATH, value="/html/body/div[3]/div[2]/h3")

    # get title
    if title.text:
        obj: str = title.text.strip()
    else:
        img: WebElement = title.find_element(by=By.XPATH, value=".//img")
        obj: str = img.text.strip()

    return obj


def get_content_from_page(driver: webdriver.Safari,path: str) -> str:

    content: WebElement = driver.find_element(by=By.XPATH, value="/html/body/div[3]/div[2]")
    html: str = content.get_attribute("innerHTML")
    soup: bs4.BeautifulSoup = bs4.BeautifulSoup(html, features="lxml")

    for query in [{"name": "h3"}, {"name": "blockquote"}, {"name": "div", "id": "carousel-numbers"}]:
        tag: Optional[Tag] = soup.find(**query)
        if tag:
            tag.decompose()
    rich_content: str = soup.get_text().strip()

    with open(file=f"{path}/content.txt", mode="w") as file:
        file.write(rich_content)

    return rich_content


def get_category_from_page(driver: webdriver.Safari) -> str:
    category: WebElement = driver.find_element(by=By.CLASS_NAME, value="category-meta")
    return category.text.strip()


def get_date_from_page(driver: webdriver.Safari) -> str:
    time_element: WebElement = driver.find_element(by=By.CLASS_NAME, value="time-meta")
    timestamp_attr = int(time_element.get_attribute("data-entrydate")) / 1000
    return datetime.datetime.fromtimestamp(timestamp_attr, tz=datetime.timezone.utc).isoformat()


def get_assets_from_page(driver: webdriver.Safari, path: str) -> List[Dict[str, str]]:

    assets: List[Dict[str, str]] = []

    # get all elements
    try:
        gallery: WebElement = driver.find_element(by=By.ID, value="gallery")
    except NoSuchElementException:
        print("No assets")
        return assets
    gallery_elements: List[WebElement] = gallery.find_elements(by=By.XPATH, value=".//*[@style]")
    for element in gallery_elements:
        style: str = element.get_attribute("style")
        url: str = URL + style.split('"')[-2][1:]
        url_obj: ParseResult = urlparse(url)
        params: Dict[str, List[str]] = parse_qs(url_obj.query)
        img_id: str = params.get("image")[0]
        entry_uuid: str = params.get("entry")[0]
        obj: Dict[str, str] = {
            "id": img_id,
            "entry_uuid": entry_uuid,
            "url": url
        }
        assets.append(obj)

    session: requests.Session = requests.Session()
    user_agent: str = driver.execute_script("return navigator.userAgent;")
    session.headers.update({"User-Agent": user_agent})

    for cookie in driver.get_cookies():
        session.cookies.set(
            name=cookie["name"], value=cookie["value"], domain=cookie["domain"]
        )

    for idx, asset in enumerate(assets):
        r: requests.Response = session.get(asset["url"])
        if r.status_code == 404:
            assets[idx]["status"] = "Unavailable"
            continue
        with open(file=f"{path}/{asset['id']}.jpeg", mode="wb") as file:
            file.write(r.content)

    return assets


def main() -> None:

    driver: webdriver.Safari = webdriver.Safari()
    driver.maximize_window()

    # login
    login_with_cookies(driver) or login_with_password(driver)
    print("logged in")

    # get page number
    pages: int = get_number_of_pages(driver)
    print(f"number of pages: {pages}")

    # get list of record ids by iterating on each page
    entries: List[str] = get_entries(driver=driver, pages=pages)
    print(f"{len(entries)} entries found")

    # dump entries
    with open(file="./entries.txt", mode="w") as file:
        for entry in entries:
            file.write(entry + "\n")
        print("Dumped entry ids to file")

    # proceed to build record
    with open(file="./entries.txt", mode="r") as file:
        entries: List[str] = file.readlines()

    for entry_id in entries:
        build_entry_json(driver=driver, entry_id=entry_id.strip())
        sleep()

    driver.close()


if __name__ == "__main__":
    main()



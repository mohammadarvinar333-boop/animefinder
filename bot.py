import os
import re
import base64
import time
import asyncio
import logging
import threading
import random
import urllib.parse
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Dict, Optional

import requests
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ تنظیمات ============
TOKEN = "8876632730:AAEplhdqqb24CPLWe6BzF0QIvMuwboQpLNI"

# ============ لیست پروکسی‌های ایران ============
IRANIAN_PROXIES = [
    {"http": "http://194.1.155.253:9080", "https": "http://194.1.155.253:9080"},
    {"http": "http://95.38.160.79:10809", "https": "http://95.38.160.79:10809"},
    {"http": "http://81.91.159.14:7776", "https": "http://81.91.159.14:7776"},
    {"http": "http://2.188.210.5:4443", "https": "http://2.188.210.5:4443"},
    {"http": "http://37.32.29.226:2080", "https": "http://37.32.29.226:2080"},
    {"http": "http://5.160.247.48:8443", "https": "http://5.160.247.48:8443"},
    {"http": "http://185.129.213.210:8080", "https": "http://185.129.213.210:8080"},
    {"http": "http://37.255.203.235:8080", "https": "http://37.255.203.235:8080"},
    {"http": "http://109.95.61.203:1080", "https": "http://109.95.61.203:1080"},
    {"http": "http://37.27.6.46:80", "https": "http://37.27.6.46:80"},
    {"http": "http://5.161.103.41:88", "https": "http://5.161.103.41:88"},
    {"http": "http://185.231.183.10:3128", "https": "http://185.231.183.10:3128"},
    {"http": "http://94.183.149.84:1180", "https": "http://94.183.149.84:1180"},
]

# ============ لاگینگ ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ کلاس جستجوگر ============
class AnimeSearcher:
    def __init__(self):
        self.genres = {
            "action": ["🔥 اکشن", "مبارزه‌ای", "جنگی"],
            "adventure": ["🗺️ ماجراجویی", "سفر", "اکتشاف"],
            "comedy": ["😂 کمدی", "طنز", "خنده‌دار"],
            "drama": ["🎭 درام", "احساسی", "غمگین"],
            "fantasy": ["🧙 فانتزی", "جادویی", "افسانه‌ای"],
            "horror": ["👻 ترسناک", "وحشت", "خونین"],
            "mystery": ["🔍 معمایی", "کارآگاهی", "پلیسی"],
            "romance": ["❤️ عاشقانه", "رمانتیک", "دل‌بر"],
            "sci_fi": ["🚀 علمی تخیلی", "فضایی", "رباتی"],
            "slice_of_life": ["📖 زندگی روزمره", "اجتماعی", "واقعی"],
            "sports": ["⚽ ورزشی", "مسابقه‌ای", "رقابتی"],
            "supernatural": ["👹 ماورایی", "فراطبیعی", "شبح"],
            "psychological": ["🧠 روانشناختی", "ذهنی", "پیچیده"],
            "thriller": ["😱 هیجانی", "مهیج", "پرتنش"],
        }

        self.popular_anime = [
            "naruto",
            "one piece",
            "bleach",
            "attack on titan",
            "demon slayer",
            "jujutsu kaisen",
            "my hero academia",
            "death note",
            "fullmetal alchemist",
            "dragon ball",
            "pokemon",
            "sailor moon",
            "hunter x hunter",
            "one punch man",
            "tokyo ghoul",
            "sword art online",
            "fairy tail",
            "gintama",
            "jojo bizarre",
            "spy x family",
            "chainsaw man",
            "vinland saga",
            "berserk",
            "evangelion",
        ]

        # سایت‌های معتبر ایرانی
        self.trusted_sites = [
            "animekhor.ir",
            "animelab.ir",
            "animeshow.ir",
            "iran-anime.ir",
            "animeworld.ir",
            "anime-4u.ir",
            "animefa.ir",
            "animedl.ir",
            "animecity.ir",
            "animeonline.ir",
            "animex.ir",
        ]

        # سایت‌های ایرانی با ساختار مشخص
        self.anime_sites = [
            {
                "name": "AnimeFa",
                "url": "https://animefa.ir",
                "search_url": "https://animefa.ir/?s={}",
                "selectors": ["article h2 a", ".post-title a", "h2.entry-title a", "a.post-link", "h2 a"],
            },
            {
                "name": "AnimeOnline",
                "url": "https://animeonline.ir",
                "search_url": "https://animeonline.ir/?s={}",
                "selectors": ["article h2 a", ".post-title a", "h2.entry-title a", "a.post-link", "h2 a"],
            },
            {
                "name": "AnimeX",
                "url": "https://animex.ir",
                "search_url": "https://animex.ir/?s={}",
                "selectors": ["article h2 a", ".post-title a", "h2.entry-title a", "a.post-link", "h2 a"],
            },
        ]

        # Cache
        self.search_cache: Dict[str, tuple] = {}
        self.cache_timeout = 600

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        ]

        self.engine_timeout = 20
        self.overall_timeout = 35

    def _get_random_proxy(self) -> Optional[Dict[str, str]]:
        """انتخاب پروکسی سالم؛ پروکسی‌های ناموفق موقتاً کنار گذاشته می‌شوند."""
        now = time.time()
        available = [
            p for p in IRANIAN_PROXIES
            if p.get("_failed_until", 0) <= now
        ]
        if not available:
            # اگر همه موقتاً fail شده‌اند، چرخه را آزاد کن
            for p in IRANIAN_PROXIES:
                p.pop("_failed_until", None)
            available = IRANIAN_PROXIES[:]
        return random.choice(available) if available else None

    def _mark_proxy_failed(self, proxy: Optional[Dict[str, str]], seconds: int = 120) -> None:
        if proxy is not None:
            proxy["_failed_until"] = time.time() + seconds

    def _headers(self, fa: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        headers["Accept-Language"] = (
            "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7"
            if fa else "en-US,en;q=0.9,fa;q=0.8"
        )
        return headers

    def _get_with_proxy(
        self,
        url: str,
        headers: Dict,
        params: Optional[Dict] = None,
        timeout: int = 15,
        proxy_attempts: int = 4,
    ) -> Optional[requests.Response]:
        """درخواست HTTP با params واقعی، retry روی چند پروکسی و fallback مستقیم."""
        last_error = None

        for _ in range(max(1, proxy_attempts)):
            proxy = self._get_random_proxy()
            if not proxy:
                break
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    proxies={"http": proxy["http"], "https": proxy["https"]},
                    timeout=timeout,
                    verify=False,
                    allow_redirects=True,
                )
                logger.info(
                    "🌐 %s -> HTTP %s%s",
                    url,
                    resp.status_code,
                    f" via {proxy['http']}" if proxy else "",
                )
                if 200 <= resp.status_code < 400:
                    return resp
                if resp.status_code in (403, 429, 500, 502, 503, 504):
                    self._mark_proxy_failed(proxy)
            except (requests.exceptions.ProxyError,
                    requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError) as e:
                last_error = e
                self._mark_proxy_failed(proxy)
                logger.warning("⚠️ پروکسی %s ناموفق: %s", proxy.get("http"), str(e)[:100])
            except requests.RequestException as e:
                last_error = e
                self._mark_proxy_failed(proxy)
                logger.warning("⚠️ خطای درخواست: %s", str(e)[:100])

        # اگر پروکسی‌ها جواب ندادند، مستقیم امتحان کن.
        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                verify=False,
                allow_redirects=True,
            )
            logger.info("🔄 درخواست مستقیم %s -> HTTP %s", url, resp.status_code)
            if 200 <= resp.status_code < 400:
                return resp
        except requests.RequestException as e:
            last_error = e
            logger.warning("❌ درخواست مستقیم ناموفق: %s", str(e)[:100])

        if last_error:
            logger.warning("❌ همه تلاش‌ها ناموفق بودند: %s", str(last_error)[:120])
        return None

    def correct_spelling(self, name: str) -> str:
        from difflib import get_close_matches
        name = name.lower().strip()
        if len(name) < 2:
            return name
        matches = get_close_matches(name, self.popular_anime, n=1, cutoff=0.6)
        return matches[0] if matches else name

    def _get_cache_key(self, anime_name: str, quality: str = None, dubbed: bool = False, uncensored: bool = False) -> str:
        return f"{anime_name}_{quality}_{dubbed}_{uncensored}"

    def _get_from_cache(self, key: str) -> Optional[List[Dict]]:
        if key in self.search_cache:
            data, timestamp = self.search_cache[key]
            if time.time() - timestamp < self.cache_timeout:
                logger.info(f"📦 استفاده از کش برای: {key}")
                return data
        return None

    def _save_to_cache(self, key: str, data: List[Dict]):
        self.search_cache[key] = (data, time.time())

    def _extract_real_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            return None
        try:
            parsed = urlparse(url)
            if "duckduckgo.com" in parsed.netloc:
                q = parse_qs(parsed.query)
                if "uddg" in q:
                    return urllib.parse.unquote(q["uddg"][0])
                if "u" in q:
                    return urllib.parse.unquote(q["u"][0])
        except Exception:
            pass
        try:
            parsed = urlparse(url)
            if "bing.com" in parsed.netloc:
                m = re.search(r"[?&]u=([^&]+)", parsed.query)
                if m:
                    enc = urllib.parse.unquote(m.group(1))
                    if enc.startswith("a1"):
                        enc = enc[2:]
                    enc += "=" * (-len(enc) % 4)
                    decoded = base64.urlsafe_b64decode(enc.encode()).decode("utf-8", "ignore")
                    if decoded.startswith("http"):
                        return decoded
        except Exception:
            pass
        return url

    def _is_iranian_site(self, url: str) -> bool:
        iranian_domains = [
            "animefa.ir", "animeonline.ir", "animex.ir", 
            "animeworld.ir", "anime-4u.ir", "animekhor.ir",
            "animelab.ir", "animeshow.ir", "iran-anime.ir",
            "animedl.ir", "animecity.ir"
        ]
        url_lower = url.lower()
        return any(domain in url_lower for domain in iranian_domains)

    def _make_result(self, url: str, title: str, anime_name: str, quality: str = None,
                     dubbed: bool = False, uncensored: bool = False, source: str = "search") -> Optional[Dict]:
        url = url.strip()
        if not url.startswith("http"):
            return None
        text = f"{title} {url}".lower()
        detected_quality = self.detect_quality(text)
        if quality and quality not in detected_quality:
            return None
        is_trusted = self._is_iranian_site(url)
        return {
            "url": url,
            "title": title or self.extract_title(url, anime_name),
            "quality": detected_quality,
            "dubbed": self.detect_dubbed(text) or dubbed,
            "uncensored": self.detect_uncensored(text) or uncensored,
            "source": source,
            "trusted": is_trusted,
        }

    # ============ جستجوی مستقیم در سایت‌های ایرانی با پروکسی ============
    def _search_iranian_sites_direct(
        self,
        anime_name: str,
        quality: str = None,
        dubbed: bool = False,
        uncensored: bool = False,
    ) -> List[Dict]:
        """جستجوی مستقیم در سایت‌های ایرانی با استفاده از پروکسی"""
        results: List[Dict] = []
        seen = set()
        headers = self._headers(fa=True)

        # ساخت کوئری‌های مختلف
        search_terms = [
            anime_name,
            anime_name.replace(" ", "-"),
            anime_name.replace(" ", "_"),
        ]

        for site in self.anime_sites:
            for term in search_terms[:4]:
                if len(results) >= 8:
                    return results

                try:
                    search_url = site["search_url"].format(quote_plus(term))
                    logger.info(f"🔍 جستجوی مستقیم در {site['name']} با پروکسی: {search_url}")

                    resp = self._get_with_proxy(search_url, headers, timeout=15)

                    if not resp or resp.status_code != 200:
                        logger.warning(f"⚠️ {site['name']} status: {resp.status_code if resp else 'No response'}")
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # حذف المان‌های غیرضروری
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    # پیدا کردن لینک‌ها با سلکتورهای مختلف
                    found_links = []
                    for selector in site.get("selectors", []):
                        links = soup.select(selector)
                        if links:
                            found_links.extend(links)
                            break

                    if not found_links:
                        found_links = soup.find_all("a", href=True)

                    logger.info(f"🔗 {site['name']}: {len(found_links)} لینک پیدا شد")

                    for link in found_links[:50]:
                        href = link.get("href", "").strip()
                        title = link.get_text(strip=True)

                        if not href:
                            continue

                        if href.startswith("/"):
                            href = site["url"] + href
                        elif href.startswith("?") or href.startswith("#"):
                            continue

                        href_lower = href.lower()

                        if not href_lower.startswith("http"):
                            continue

                        # فیلتر لینک‌های بی‌ربط
                        bad_patterns = [
                            "wa.me", "mailto:", "javascript:", "tel:",
                            "/wp-", "/category", "/tag", "/author",
                            "/feed", "/page/", "/cdn-cgi/", "/wp-content",
                            "?lang=", "&lang=", "/login", "/register",
                            "/cart", "/checkout", "/profile", "/cdn-cgi/"
                        ]
                        if any(p in href_lower for p in bad_patterns):
                            continue

                        if href_lower.rstrip("/") == site["url"].lower().rstrip("/"):
                            continue

                        # بررسی ارتباط با انیمه
                        title_lower = title.lower()
                        anime_lower = anime_name.lower()

                        is_related = (
                            anime_lower in title_lower or
                            anime_lower in href_lower or
                            any(word in title_lower for word in anime_lower.split()) or
                            "دانلود" in href or "download" in href_lower or
                            "anime" in href_lower
                        )

                        if not is_related and len(title) < 4:
                            continue

                        if len(title) < 2:
                            continue

                        item = self._make_result(
                            href,
                            title,
                            anime_name,
                            quality,
                            dubbed,
                            uncensored,
                            site["name"],
                        )

                        if item and item["url"] not in seen:
                            seen.add(item["url"])
                            item["trusted"] = True
                            results.append(item)
                            logger.info(f"✅ پیدا شد در {site['name']}: {title[:50]}")
                            if len(results) >= 8:
                                return results

                except Exception as e:
                    logger.warning(f"خطا در جستجوی {site['name']}: {str(e)[:100]}")
                    continue

        return results

    # ============ جستجو با DuckDuckGo ============
    def _search_duckduckgo(
        self,
        queries: List[str],
        anime_name: str,
        quality: str = None,
        dubbed: bool = False,
        uncensored: bool = False,
    ) -> List[Dict]:
        results: List[Dict] = []
        seen = set()
        headers = self._headers(fa=True)

        for query in queries:
            if len(results) >= 12:
                break

            try:
                resp = self._get_with_proxy(
                    "https://html.duckduckgo.com/html/",
                    headers,
                    params={"q": query},
                    timeout=self.engine_timeout,
                )

                if not resp or resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a.result__a")

                for link in links[:25]:
                    href = link.get("href", "").strip()
                    if not href or href in seen:
                        continue

                    real = self._extract_real_url(href)
                    if not real or real in seen:
                        continue

                    seen.add(real)
                    item = self._make_result(
                        real,
                        link.get_text(strip=True),
                        anime_name,
                        quality,
                        dubbed,
                        uncensored,
                        "DuckDuckGo",
                    )
                    if item:
                        results.append(item)
                        if len(results) >= 12:
                            break

            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Timeout DuckDuckGo: {query[:40]}")
            except Exception as e:
                logger.warning(f"خطا در DuckDuckGo: {str(e)[:80]}")
                continue

        return results

    # ============ جستجو با Bing ============
    def _search_bing(
        self,
        query: str,
        anime_name: str,
        quality: str = None,
        dubbed: bool = False,
        uncensored: bool = False,
    ) -> List[Dict]:
        results: List[Dict] = []
        seen = set()
        headers = self._headers()

        try:
            resp = self._get_with_proxy(
                "https://www.bing.com/search",
                headers,
                params={"q": query, "count": 25},
                timeout=self.engine_timeout,
            )

            if not resp or resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("li.b_algo h2 a")[:25]:
                real = self._extract_real_url(a.get("href", ""))
                if not real or real in seen:
                    continue
                seen.add(real)
                item = self._make_result(
                    real,
                    a.get_text(strip=True),
                    anime_name,
                    quality,
                    dubbed,
                    uncensored,
                    "Bing",
                )
                if item:
                    results.append(item)

        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout Bing: {query[:40]}")
        except Exception as e:
            logger.warning(f"خطا در Bing: {str(e)[:80]}")

        return results

    # ============ جستجو با Mojeek ============
    def _search_mojeek(
        self,
        query: str,
        anime_name: str,
        quality: str = None,
        dubbed: bool = False,
        uncensored: bool = False,
    ) -> List[Dict]:
        results: List[Dict] = []
        seen = set()
        headers = self._headers()

        try:
            resp = self._get_with_proxy(
                "https://www.mojeek.com/search",
                headers,
                params={"q": query},
                timeout=self.engine_timeout,
            )

            if not resp or resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("ul.results-standard li h2 a")[:25]:
                real = self._extract_real_url(a.get("href", ""))
                if not real or real in seen:
                    continue
                seen.add(real)
                item = self._make_result(
                    real,
                    a.get_text(strip=True),
                    anime_name,
                    quality,
                    dubbed,
                    uncensored,
                    "Mojeek",
                )
                if item:
                    results.append(item)

        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout Mojeek: {query[:40]}")
        except Exception as e:
            logger.warning(f"خطا در Mojeek: {str(e)[:80]}")

        return results

    def search_google(
        self,
        anime_name: str,
        quality: str = None,
        dubbed: bool = False,
        uncensored: bool = False,
    ) -> List[Dict]:
        cache_key = self._get_cache_key(anime_name, quality, dubbed, uncensored)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result

        logger.info(f"🔍 جستجوی هم‌زمان برای: {anime_name}")

        persian_query = f'"{anime_name}" انیمه دانلود'
        if quality:
            persian_query += f" {quality}"
        if dubbed:
            persian_query += " دوبله فارسی"
        if uncensored:
            persian_query += " بدون سانسور"

        # چند کوئری مکمل برای سایت‌های ایرانی؛ موتور جستجو ممکن است عبارت فارسی/انگلیسی را متفاوت ایندکس کرده باشد.
        iran_queries = [
            persian_query,
            f"{anime_name} دانلود انیمه",
            f"{anime_name} site:ir انیمه",
        ]
        english_query = f"{anime_name} anime download"
        if dubbed:
            english_query += " dubbed"

        all_results: List[Dict] = []

        # ========== اولویت: جستجوی مستقیم در سایت‌های ایرانی با پروکسی ==========
        logger.info("🇮🇷 جستجوی مستقیم در سایت‌های ایرانی با پروکسی...")
        direct_results = self._search_iranian_sites_direct(anime_name, quality, dubbed, uncensored)
        all_results.extend(direct_results)
        logger.info(f"🇮🇷 {len(direct_results)} نتیجه از سایت‌های ایرانی (مستقیم)")

        # ========== جستجو در موتورهای جستجو ==========
        logger.info("🌐 جستجو در موتورهای جستجو...")
        executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="search")
        futures = []
        try:
            futures.append(
                executor.submit(
                    self._search_duckduckgo,
                    iran_queries + [english_query],
                    anime_name, quality, dubbed, uncensored,
                )
            )
            futures.append(
                executor.submit(
                    self._search_bing, persian_query, anime_name, quality, dubbed, uncensored
                )
            )
            futures.append(
                executor.submit(
                    self._search_bing, f"{anime_name} site:ir انیمه دانلود", anime_name, quality, dubbed, uncensored
                )
            )
            futures.append(
                executor.submit(
                    self._search_bing, english_query, anime_name, quality, dubbed, uncensored
                )
            )
            futures.append(
                executor.submit(
                    self._search_mojeek, english_query, anime_name, quality, dubbed, uncensored
                )
            )

            deadline = time.time() + self.overall_timeout
            for future in as_completed(futures):
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    res = future.result(timeout=max(0.1, remaining))
                    if res:
                        all_results.extend(res)
                except Exception as e:
                    logger.warning(f"جستجو ناموفق: {str(e)[:80]}")
        finally:
            executor.shutdown(wait=False)

        # حذف URLهای تکراری
        merged: List[Dict] = []
        seen = set()
        for r in all_results:
            u = r["url"]
            if u in seen:
                continue
            seen.add(u)
            merged.append(r)

        # مرتب‌سازی: اول سایت‌های معتبر، بعد کیفیت بالاتر
        quality_order = {"4K": 0, "1080p": 1, "720p": 2, "480p": 3, "متغیر": 4}
        merged.sort(key=lambda x: (not x.get("trusted", False), quality_order.get(x["quality"], 5)))

        final = merged[:12]
        if final:
            self._save_to_cache(cache_key, final)
            trusted_count = len([r for r in final if r.get("trusted", False)])
            logger.info(f"✅ {len(final)} نتیجه نهایی ({trusted_count} مورد از سایت‌های ایرانی)")

        return final

    def extract_title(self, url: str, default_name: str) -> str:
        try:
            url_parts = url.split("/")
            for part in url_parts:
                if any(anime in part.lower() for anime in self.popular_anime):
                    title = part.replace("-", " ").replace("_", " ").replace("%20", " ").title()
                    if len(title) > 3:
                        return title
            return default_name.title()
        except Exception:
            return default_name.title()

    def detect_quality(self, text: str) -> str:
        text_lower = text.lower()
        if "4k" in text_lower or "2160" in text_lower or "8k" in text_lower:
            return "4K"
        elif "1080" in text_lower or "1080p" in text_lower:
            return "1080p"
        elif "720" in text_lower or "720p" in text_lower:
            return "720p"
        elif "480" in text_lower or "480p" in text_lower:
            return "480p"
        return "متغیر"

    def detect_dubbed(self, text: str) -> bool:
        text_lower = text.lower()
        keywords = ["دوبله", "dubbed", "dub", "persian", "فارسی", "farsi"]
        return any(keyword in text_lower for keyword in keywords)

    def detect_uncensored(self, text: str) -> bool:
        text_lower = text.lower()
        keywords = ["uncensored", "بدون سانسور", "بی‌سانسور", "without censorship"]
        return any(keyword in text_lower for keyword in keywords)


# ============ کلاس اصلی ربات ============
class AnimeBot:
    def __init__(self):
        self.searcher = AnimeSearcher()
        self.user_data: Dict[int, Dict] = {}
        self.user_search_lock: Dict[int, bool] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data="advanced_search")],
            [InlineKeyboardButton("📂 جستجوی ژانر", callback_data="genres")],
            [InlineKeyboardButton("⚙️ فیلترها", callback_data="filters")],
            [InlineKeyboardButton("🏆 محبوب‌ترین‌ها", callback_data="popular")],
            [InlineKeyboardButton("❓ راهنما", callback_data="help")],
        ]

        welcome_text = (
            "🎬 **به ربات جستجوگر انیمه خوش آمدید!**\n\n"
            "✨ **قابلیت‌ها:**\n"
            "• جستجو در سایت‌های معتبر ایرانی ⭐\n"
            "• جستجو در DuckDuckGo و Bing\n"
            "• لینک دانلود مستقیم\n"
            "• کیفیت‌های مختلف\n"
            "• تشخیص دوبله و زیرنویس\n"
            "• فیلتر بدون سانسور\n"
            "• جستجوی ژانر\n"
            "• اصلاح املایی هوشمند\n\n"
            "📝 **اسم انیمه رو تایپ کن یا از دکمه‌ها استفاده کن!**\n"
            "⭐ = سایت ایرانی"
        )

        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query_text = update.message.text.strip()
        user_id = update.effective_user.id

        if not query_text or len(query_text) < 2:
            await update.message.reply_text(
                "❌ لطفاً اسم انیمه رو درست وارد کن!\nمثال: `Attack on Titan`",
                parse_mode="Markdown",
            )
            return

        if self.user_search_lock.get(user_id, False):
            logger.warning(f"⛔ کاربر {user_id} در حال جستجو است و دوباره تلاش کرد")
            await update.message.reply_text(
                "⏳ **لطفاً صبر کنید!**\n"
                "شما در حال حاضر یک جستجو در حال انجام دارید.\n"
                "پس از اتمام جستجوی قبلی، می‌توانید دوباره تلاش کنید.",
                parse_mode="Markdown",
            )
            return

        self.user_search_lock[user_id] = True
        logger.info(f"🔒 کاربر {user_id} قفل شد (شروع جستجو)")

        try:
            msg = await update.message.reply_text(
                f"🔍 در حال جستجوی «{query_text}»...\n⏳ لطفاً چند لحظه صبر کنید...",
                parse_mode="Markdown",
            )

            corrected_name = self.searcher.correct_spelling(query_text)

            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            self.user_data[user_id]["last_search"] = corrected_name
            self.user_data[user_id].setdefault("filters", {})

            filters_data = self.user_data[user_id]["filters"]
            quality = filters_data.get("quality")
            dubbed = filters_data.get("dubbed", False)
            uncensored = filters_data.get("uncensored", False)

            results = await asyncio.to_thread(
                self.searcher.search_google,
                corrected_name,
                quality=quality,
                dubbed=dubbed,
                uncensored=uncensored,
            )

            if not results:
                await msg.edit_text(
                    f"❌ متأسفم! انیمه «{query_text}» پیدا نشد.\n\n"
                    f"💡 **راهکارها:**\n"
                    f"• اسم انگلیسی رو امتحان کن\n"
                    f"• از جستجوی پیشرفته استفاده کن\n"
                    f"• از جستجوی ژانر استفاده کن\n\n"
                    f"🔄 پیشنهاد: `{corrected_name}`",
                    parse_mode="Markdown",
                )
                return

            await self.show_results(msg, corrected_name, results, user_id)

        except Exception as e:
            logger.error(f"❌ خطا در جستجو برای کاربر {user_id}: {e}")
            await update.message.reply_text(
                "❌ خطایی در جستجو رخ داد. لطفاً دوباره تلاش کنید.",
                parse_mode="Markdown",
            )
        finally:
            self.user_search_lock[user_id] = False
            logger.info(f"🔓 کاربر {user_id} آزاد شد (پایان جستجو)")

    async def show_results(self, msg, anime_name: str, results: List[Dict], user_id: int):
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id]["results"] = results

        # اولویت با سایت‌های ایرانی
        trusted_results = [r for r in results if r.get("trusted", False)]
        other_results = [r for r in results if not r.get("trusted", False)]
        display_results = (trusted_results + other_results)[:5]

        result_text = f"🎯 **نتایج جستجوی «{anime_name}»**\n"
        result_text += f"🔎 {len(results)} نتیجه پیدا شد\n\n"

        for i, result in enumerate(display_results, 1):
            quality_icons = {"1080p": "📺", "720p": "💻", "480p": "📱", "4K": "🖥️", "متغیر": "📹"}
            quality_icon = quality_icons.get(result["quality"], "📹")

            dub_text = "🎙️ دوبله فارسی" if result["dubbed"] else "📝 زیرنویس"
            censored_text = "🔞 بدون سانسور" if result["uncensored"] else "✅ سانسور شده"
            trusted_icon = "⭐ " if result.get("trusted", False) else ""
            source_text = f"📌 منبع: {result.get('source', 'ناشناس')}"

            result_text += f"{i}. {quality_icon} **{result['title']}** {trusted_icon}\n"
            result_text += f"   📥 کیفیت: {result['quality']}\n"
            result_text += f"   {dub_text}\n"
            result_text += f"   {censored_text}\n"
            result_text += f"   {source_text}\n"
            result_text += f"   🔗 [لینک دانلود]({result['url']})\n\n"

        keyboard = []
        for i in range(min(5, len(display_results))):
            quality = display_results[i]["quality"]
            keyboard.append([InlineKeyboardButton(f"📥 دانلود گزینه {i+1} ({quality})", callback_data=f"download_{i}")])

        keyboard.append([InlineKeyboardButton("🔄 جستجوی جدید", callback_data="new_search")])
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")])

        await msg.edit_text(
            result_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    # ============ بقیه متدها ============
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id

        try:
            await query.answer()
        except Exception as e:
            logger.warning(f"⚠️ خطا در پاسخ به کوئری: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="⏰ زمان این دکمه منقضی شده است. لطفاً دوباره از منوی اصلی استفاده کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]])
            )
            return

        data = query.data

        if data == "main_menu":
            await self.show_main_menu(query)
        elif data == "simple_search":
            await query.edit_message_text(
                "🔍 **جستجوی ساده**\n\nاسم انیمه مورد نظر رو تایپ کن.\nمثال: `Naruto`",
                parse_mode="Markdown",
            )
        elif data == "advanced_search":
            await self.show_advanced_search(query)
        elif data == "genres":
            await self.show_genres(query)
        elif data == "filters":
            await self.show_filters(query)
        elif data == "popular":
            await self.show_popular(query)
        elif data == "help":
            await self.show_help(query)
        elif data == "new_search":
            await query.edit_message_text("🔍 اسم انیمه مورد نظر رو تایپ کن:")
        elif data.startswith("genre_"):
            genre = data.replace("genre_", "")
            await self.search_by_genre(query, genre)
        elif data.startswith("download_"):
            await self.download_file(query, user_id)
        elif data == "filter_dubbed":
            await self.apply_filter(query, user_id, "dubbed")
        elif data == "filter_1080":
            await self.apply_filter(query, user_id, "1080p")
        elif data == "filter_720":
            await self.apply_filter(query, user_id, "720p")
        elif data == "filter_uncensored":
            await self.apply_filter(query, user_id, "uncensored")

    async def show_main_menu(self, query):
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data="advanced_search")],
            [InlineKeyboardButton("📂 جستجوی ژانر", callback_data="genres")],
            [InlineKeyboardButton("⚙️ فیلترها", callback_data="filters")],
            [InlineKeyboardButton("🏆 محبوب‌ترین‌ها", callback_data="popular")],
            [InlineKeyboardButton("❓ راهنما", callback_data="help")],
        ]
        await query.edit_message_text(
            "🎬 **منوی اصلی**\n\nیکی از گزینه‌های زیر رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def show_advanced_search(self, query):
        keyboard = [
            [InlineKeyboardButton("🎙️ دوبله فارسی", callback_data="filter_dubbed")],
            [InlineKeyboardButton("📺 کیفیت 1080p", callback_data="filter_1080")],
            [InlineKeyboardButton("📺 کیفیت 720p", callback_data="filter_720")],
            [InlineKeyboardButton("🚫 بدون سانسور", callback_data="filter_uncensored")],
            [InlineKeyboardButton("🔍 شروع جستجو", callback_data="simple_search")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            "🎯 **جستجوی پیشرفته**\n\nفیلترهای مورد نظر رو انتخاب کن، سپس روی «شروع جستجو» بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def show_genres(self, query):
        keyboard = []
        for genre_en, genre_list in self.searcher.genres.items():
            display_name = genre_list[0] if genre_list else genre_en
            keyboard.append([InlineKeyboardButton(display_name, callback_data=f"genre_{genre_en}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
        await query.edit_message_text(
            "🎬 **انتخاب ژانر**\n\nژانر مورد نظر رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def search_by_genre(self, query, genre: str):
        user_id = query.from_user.id

        if self.user_search_lock.get(user_id, False):
            logger.warning(f"⛔ کاربر {user_id} در حال جستجو است و دوباره تلاش کرد (ژانر)")
            await query.edit_message_text(
                "⏳ **لطفاً صبر کنید!**\nشما در حال حاضر یک جستجو در حال انجام دارید.\nپس از اتمام جستجوی قبلی، می‌توانید دوباره تلاش کنید.",
                parse_mode="Markdown",
            )
            return

        self.user_search_lock[user_id] = True
        logger.info(f"🔒 کاربر {user_id} قفل شد (جستجوی ژانر)")

        try:
            genre_names = self.searcher.genres.get(genre, [genre])
            genre_name = genre_names[0] if genre_names else genre

            await query.edit_message_text(f"🔍 در حال جستجوی انیمه‌های ژانر «{genre_name}»...\n⏳ لطفاً صبر کنید...")

            results = await asyncio.to_thread(self.searcher.search_google, genre_name)

            if results:
                await self.show_results(query.message, f"ژانر {genre_name}", results, query.from_user.id)
            else:
                await query.edit_message_text(
                    f"❌ متأسفم! انیمه‌ای با ژانر «{genre_name}» پیدا نشد.\n🔄 ژانر دیگری را امتحان کن یا از جستجوی ساده استفاده کن."
                )

        except Exception as e:
            logger.error(f"❌ خطا در جستجوی ژانر برای کاربر {user_id}: {e}")
            await query.edit_message_text("❌ خطایی در جستجو رخ داد. لطفاً دوباره تلاش کنید.", parse_mode="Markdown")
        finally:
            self.user_search_lock[user_id] = False
            logger.info(f"🔓 کاربر {user_id} آزاد شد (پایان جستجوی ژانر)")

    async def show_filters(self, query):
        user_id = query.from_user.id
        filters_data = self.user_data.get(user_id, {}).get("filters", {})

        dubbed = filters_data.get("dubbed", False)
        quality = filters_data.get("quality")
        uncensored = filters_data.get("uncensored", False)

        status_text = "⚙️ **وضعیت فیلترها:**\n\n"
        status_text += f"🎙️ دوبله فارسی: {'✅ فعال' if dubbed else '❌ غیرفعال'}\n"
        status_text += f"📺 کیفیت: {quality if quality else '🎛 هر کیفیت'}\n"
        status_text += f"🚫 بدون سانسور: {'✅ فعال' if uncensored else '❌ غیرفعال'}\n\n"
        status_text += "برای تغییر فیلترها از دکمه‌های جستجوی پیشرفته استفاده کن."

        keyboard = [
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data="advanced_search")],
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
        ]

        await query.edit_message_text(
            status_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def show_popular(self, query):
        text = "🏆 **محبوب‌ترین انیمه‌ها:**\n\n"
        for i, name in enumerate(self.searcher.popular_anime[:15], 1):
            text += f"{i}. {name.title()}\n"
        text += "\n📝 یکی از اسم‌ها رو کپی کن و در چت ارسال کن تا برات جستجو کنم."

        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def show_help(self, query):
        help_text = (
            "❓ **راهنمای ربات جستجوگر انیمه**\n\n"
            "🔍 جستجوی ساده:\n• فقط اسم انیمه رو تایپ کن (ترجیحاً انگلیسی)\n\n"
            "🎯 جستجوی پیشرفته:\n• فیلتر دوبله فارسی\n• فیلتر کیفیت 1080p و 720p\n• فیلتر بدون سانسور\n\n"
            "📂 جستجوی ژانر:\n• انتخاب ژانر مثل اکشن، کمدی، درام و...\n\n"
            "🏆 محبوب‌ترین‌ها:\n• نمایش لیست انیمه‌های معروف برای شروع\n\n"
            "⭐ سایت‌های ایرانی با ستاره مشخص شدن\n\n"
            "اگر نتیجه‌ای پیدا نشد، اسم رو ساده‌تر یا انگلیسی‌تر وارد کن."
        )

        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
        ]

        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def apply_filter(self, query, user_id: int, filter_type: str):
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        filters_data = self.user_data[user_id].setdefault("filters", {})

        if filter_type == "dubbed":
            filters_data["dubbed"] = not filters_data.get("dubbed", False)
        elif filter_type in ("1080p", "720p"):
            current_quality = filters_data.get("quality")
            if current_quality == filter_type:
                filters_data["quality"] = None
            else:
                filters_data["quality"] = filter_type
        elif filter_type == "uncensored":
            filters_data["uncensored"] = not filters_data.get("uncensored", False)

        status = "✅ فیلترها به‌روزرسانی شدند.\n\n"
        status += f"🎙️ دوبله فارسی: {'فعال' if filters_data.get('dubbed') else 'غیرفعال'}\n"
        status += f"📺 کیفیت: {filters_data.get('quality') or 'هر کیفیت'}\n"
        status += f"🚫 بدون سانسور: {'فعال' if filters_data.get('uncensored') else 'غیرفعال'}\n\n"
        status += "حالا می‌تونی اسم انیمه رو تایپ کنی تا با این فیلترها جستجو بشه."

        keyboard = [
            [InlineKeyboardButton("🔍 شروع جستجو", callback_data="simple_search")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="advanced_search")],
        ]

        await query.edit_message_text(
            status,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def download_file(self, query, user_id: int):
        data = query.data
        if user_id not in self.user_data or "results" not in self.user_data[user_id]:
            await query.edit_message_text(
                "❌ هیچ نتیجه‌ای برای دانلود موجود نیست.\n🔍 اول یک جستجو انجام بده.",
                parse_mode="Markdown",
            )
            return

        try:
            index = int(data.split("_")[1])
        except (IndexError, ValueError):
            await query.edit_message_text(
                "❌ خطا در انتخاب گزینه دانلود.\nدوباره تلاش کن.",
                parse_mode="Markdown",
            )
            return

        results = self.user_data[user_id]["results"]
        if index < 0 or index >= len(results):
            await query.edit_message_text(
                "❌ گزینه انتخاب‌شده معتبر نیست.",
                parse_mode="Markdown",
            )
            return

        result = results[index]
        text = (
            f"📥 **دانلود انیمه انتخاب‌شده**\n\n"
            f"🎬 عنوان: {result['title']}\n"
            f"📺 کیفیت: {result['quality']}\n"
            f"🎙️ {'دوبله فارسی' if result['dubbed'] else 'زیرنویس'}\n"
            f"🚫 {'بدون سانسور' if result['uncensored'] else 'سانسور شده'}\n"
            f"📌 منبع: {result.get('source', 'ناشناس')}\n\n"
            f"🔗 لینک دانلود:\n{result['url']}\n\n"
            "اگر لینک باز نشد، آن را در مرورگر باز کن."
        )

        keyboard = [
            [InlineKeyboardButton("🔄 جستجوی جدید", callback_data="new_search")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )


# ============ سرور سلامت ============
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"✅ سرور سلامت روی پورت {port} راه‌اندازی شد.")
    server.serve_forever()


# ============ تابع اصلی اجرای ربات (اصلاح شده برای رفع Conflict) ============
async def run_bot():
    bot = AnimeBot()
    
    application = (
        Application.builder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_search)
    )
    application.add_handler(CallbackQueryHandler(bot.handle_callback))

    logger.info("🤖 ربات انیمه راه‌اندازی شد!")

    # ========== راه‌اندازی با حذف Webhook برای جلوگیری از Conflict ==========
    try:
        # حذف Webhook قبلی با drop_pending_updates=True
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook پاک شد")
        
        # کمی صبر کن تا مطمئن بشی
        await asyncio.sleep(2)
        
        # راه‌اندازی Application
        await application.initialize()
        await application.start()
        
        # شروع Polling با تنظیمات ضد Conflict
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=0.5,
        )
        
        logger.info("✅ ربات با موفقیت راه‌اندازی شد!")
        
        # منتظر ماندن
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("🛑 در حال توقف ربات...")
    except telegram.error.Conflict as e:
        logger.error(f"❌ خطای Conflict: {e}")
        logger.info("🔄 در حال تلاش مجدد بعد از 5 ثانیه...")
        await asyncio.sleep(5)
        # تلاش مجدد
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
            await application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
                poll_interval=0.5,
            )
            while True:
                await asyncio.sleep(1)
        except Exception as retry_error:
            logger.error(f"❌ تلاش مجدد ناموفق: {retry_error}")
    except Exception as e:
        logger.error(f"❌ خطا در اجرای ربات: {e}")
    finally:
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except:
            pass
        logger.info("🛑 ربات متوقف شد.")


# ============ تابع اصلی ============
def main():
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 ربات متوقف شد.")
    except Exception as e:
        logger.error(f"❌ خطا در اجرای ربات: {e}")
        raise


if __name__ == "__main__":
    main()

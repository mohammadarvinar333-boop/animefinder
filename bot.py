import os
import re
import json
import time
import asyncio
import logging
import threading
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Dict, Optional
from datetime import datetime

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

# ============ تنظیمات ============
TOKEN = "8876632730:AAEplhdqqb24CPLWe6BzF0QIvMuwboQpLNI"
DEEPSEEK_API_KEY = "4da13db8-d107-437f-846b-9c8219888519"  # API Key شما

# ============ لاگینگ ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ کلاس DeepSeek API ============
class DeepSeekClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    def get_anime_info(self, anime_name: str) -> Dict:
        """دریافت اطلاعات انیمه از DeepSeek"""
        try:
            prompt = f"""
            لطفاً اطلاعات زیر را درباره انیمه "{anime_name}" به صورت JSON ارائه دهید:
            1. نام انگلیسی
            2. نام ژاپنی
            3. ژانرها
            4. خلاصه داستان (حدود 100 کلمه)
            5. تعداد قسمت‌ها
            6. سال انتشار
            7. امتیاز (از 10)
            8. استودیو سازنده
            9. کارگردان
            10. وضعیت (در حال پخش/به پایان رسیده)
            11. لینک‌های دانلود معتبر (حداکثر 3 عدد)
            
            پاسخ را فقط به صورت JSON خام بده، بدون توضیحات اضافی.
            """
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful anime information assistant. Provide information in Persian language only, in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 800
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # استخراج JSON از پاسخ
                try:
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        info = json.loads(json_match.group())
                        return info
                except:
                    # اگر JSON نبود، یک دیکشنری ساده بساز
                    return {"title": anime_name, "description": content, "source": "deepseek"}
                    
            return None
            
        except Exception as e:
            logger.error(f"خطا در DeepSeek: {e}")
            return None
    
    def search_anime(self, query: str) -> List[Dict]:
        """جستجوی انیمه با استفاده از DeepSeek"""
        try:
            prompt = f"""
            لطفاً انیمه‌های مرتبط با عبارت "{query}" را پیدا کن.
            برای هر انیمه، اطلاعات زیر را به صورت JSON ارائه بده:
            1. نام انیمه
            2. ژانر
            3. سال انتشار
            4. امتیاز
            5. خلاصه کوتاه
            
            حداکثر 5 انیمه را معرفی کن.
            پاسخ را فقط به صورت JSON Array بده.
            """
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are an anime search assistant. Provide results in Persian language as a JSON array."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.5,
                "max_tokens": 1000
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=25
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                try:
                    # استخراج JSON Array
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        results = json.loads(json_match.group())
                        return results
                except:
                    pass
                    
            return []
            
        except Exception as e:
            logger.error(f"خطا در جستجوی DeepSeek: {e}")
            return []

# ============ کلاس جستجوگر ============
class AnimeSearcher:
    def __init__(self, deepseek_client: DeepSeekClient = None):
        self.deepseek = deepseek_client
        
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
        ]

        self.search_cache: Dict[str, tuple] = {}
        self.cache_timeout = 600

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        ]

        self.anime_sites = [
            {"name": "AnimeKhor", "url": "https://animekhor.ir", "search_url": "https://animekhor.ir/?s={}"},
            {"name": "AnimeLab", "url": "https://animelab.ir", "search_url": "https://animelab.ir/?s={}"},
            {"name": "AnimeShow", "url": "https://animeshow.ir", "search_url": "https://animeshow.ir/?s={}"},
            {"name": "IranAnime", "url": "https://iran-anime.ir", "search_url": "https://iran-anime.ir/?s={}"},
            {"name": "AnimeWorld", "url": "https://animeworld.ir", "search_url": "https://animeworld.ir/?s={}"},
        ]

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

    def search_google(self, anime_name: str, quality: str = None, dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        cache_key = self._get_cache_key(anime_name, quality, dubbed, uncensored)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result

        results: List[Dict] = []

        # روش 1: استفاده از DeepSeek برای جستجوی هوشمند
        if self.deepseek:
            logger.info(f"🤖 جستجوی هوشمند با DeepSeek برای: {anime_name}")
            deepseek_results = self.deepseek.search_anime(anime_name)
            if deepseek_results:
                for item in deepseek_results:
                    # تبدیل نتایج DeepSeek به فرمت استاندارد
                    results.append({
                        "url": f"https://myanimelist.net/anime.php?q={quote_plus(item.get('name', anime_name))}",
                        "title": item.get('name', anime_name),
                        "quality": "متغیر",
                        "dubbed": dubbed,
                        "uncensored": uncensored,
                        "source": "DeepSeek AI",
                        "trusted": True,
                        "extra_info": {
                            "genre": item.get('ژانر', 'نامشخص'),
                            "year": item.get('سال انتشار', 'نامشخص'),
                            "rating": item.get('امتیاز', 'نامشخص'),
                            "summary": item.get('خلاصه کوتاه', '')
                        }
                    })
                if results:
                    self._save_to_cache(cache_key, results[:5])
                    return results[:5]

        # روش 2: DuckDuckGo API
        logger.info(f"🔍 جستجو در DuckDuckGo برای: {anime_name}")
        query = f'"{anime_name}" انیمه دانلود لینک مستقیم'
        if quality:
            query += f" {quality}"
        if dubbed:
            query += " دوبله فارسی"
        if uncensored:
            query += " بدون سانسور"
        results = self._duckduckgo_search(query, anime_name, quality, dubbed, uncensored)

        # روش 3: جستجو در سایت‌های ایرانی
        if not results:
            logger.info("🔄 جستجو در سایت‌های معتبر ایرانی")
            results = self._search_trusted_sites(anime_name, quality, dubbed, uncensored)

        # روش 4: جستجوی ساده
        if not results:
            logger.info("🔄 جستجوی ساده")
            results = self._simple_search(anime_name, quality, dubbed, uncensored)

        # مرتب‌سازی نتایج
        results.sort(key=lambda x: (not x["trusted"], x["quality"] != "1080p"))

        if results:
            self._save_to_cache(cache_key, results[:10])

        return results[:10]

    def _simple_search(self, anime_name: str, quality: str = None, dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        """جستجوی ساده با لینک‌های پیش‌فرض"""
        results = []
        
        # اضافه کردن لینک‌های پیش‌فرض
        default_links = [
            f"https://www.google.com/search?q={quote_plus(anime_name)}+انیمه+دانلود",
            f"https://myanimelist.net/anime.php?q={quote_plus(anime_name)}",
        ]
        
        for url in default_links:
            results.append({
                "url": url,
                "title": f"جستجوی {anime_name} در گوگل",
                "quality": "متغیر",
                "dubbed": dubbed,
                "uncensored": uncensored,
                "source": "پیش‌فرض",
                "trusted": False,
            })
            
        return results

    def _search_trusted_sites(self, anime_name: str, quality: str = None, dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        results: List[Dict] = []
        seen_urls = set()

        for site in self.anime_sites:
            try:
                search_url = site["search_url"].format(quote_plus(anime_name))
                headers = {
                    "User-Agent": random.choice(self.user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
                }

                time.sleep(random.uniform(0.5, 1))
                response = requests.get(search_url, headers=headers, timeout=10)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link.get("href", "")
                        title = link.get_text(strip=True)

                        if href and ("anime" in href.lower() or "دانلود" in href):
                            if href.startswith("/"):
                                href = site["url"] + href

                            if href in seen_urls:
                                continue
                            seen_urls.add(href)

                            detected_quality = self.detect_quality(href)
                            if quality and quality not in detected_quality:
                                continue

                            is_trusted = True
                            results.append({
                                "url": href,
                                "title": title or self.extract_title(href, anime_name),
                                "quality": detected_quality,
                                "dubbed": self.detect_dubbed(href) or dubbed,
                                "uncensored": self.detect_uncensored(href) or uncensored,
                                "source": site["name"],
                                "trusted": is_trusted,
                            })

                            if len(results) >= 5:
                                break

            except Exception as e:
                logger.warning(f"خطا در جستجوی {site['name']}: {e}")
                continue

        return results

    def _duckduckgo_search(self, query: str, anime_name: str, quality: str = None, dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        results: List[Dict] = []
        seen_urls = set()

        for attempt in range(2):
            try:
                logger.info(f"جستجوی DuckDuckGo: {query} (تلاش {attempt+1})")
                
                # استفاده از API DuckDuckGo
                url = "https://api.duckduckgo.com/"
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1
                }

                headers = {"User-Agent": random.choice(self.user_agents)}
                response = requests.get(url, params=params, headers=headers, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    
                    if "RelatedTopics" in data:
                        for topic in data["RelatedTopics"][:10]:
                            if "Result" in topic:
                                result_text = topic.get("Result", "")
                                if "http" in result_text:
                                    import re
                                    urls = re.findall(r'https?://[^\s<>"]+', result_text)
                                    for link_url in urls[:3]:
                                        if link_url and link_url.startswith("http"):
                                            if link_url in seen_urls:
                                                continue
                                            seen_urls.add(link_url)
                                            
                                            is_trusted = any(site in link_url for site in self.trusted_sites)
                                            results.append({
                                                "url": link_url,
                                                "title": topic.get("Text", anime_name.title()),
                                                "quality": self.detect_quality(link_url),
                                                "dubbed": self.detect_dubbed(link_url) or dubbed,
                                                "uncensored": self.detect_uncensored(link_url) or uncensored,
                                                "source": "duckduckgo_api",
                                                "trusted": is_trusted,
                                            })

                    if results:
                        break

            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Timeout در DuckDuckGo (تلاش {attempt+1})")
                time.sleep(2)
            except Exception as e:
                logger.warning(f"خطا در DuckDuckGo (تلاش {attempt+1}): {e}")
                time.sleep(2)

        if not results:
            results = self._duckduckgo_html_search(query, anime_name, quality, dubbed, uncensored)

        return results

    def _duckduckgo_html_search(self, query: str, anime_name: str, quality: str = None, dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        results: List[Dict] = []
        seen_urls = set()

        try:
            logger.info(f"جستجوی HTML DuckDuckGo: {query}")
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}

            headers = {
                "User-Agent": random.choice(self.user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
            }

            response = requests.get(url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.select("a.result__a")[:10]:
                    link_url = link.get("href", "")

                    if link_url and link_url.startswith("//duckduckgo.com/l/"):
                        try:
                            parsed = urlparse(link_url)
                            query_params = parse_qs(parsed.query)
                            if "uddg" in query_params:
                                import urllib.parse
                                uddg = query_params["uddg"][0]
                                decoded = urllib.parse.unquote(uddg)
                                if "http" in decoded:
                                    link_url = decoded.split("http")[1]
                                    link_url = "http" + link_url
                                    if "&" in link_url:
                                        link_url = link_url.split("&")[0]
                        except Exception:
                            pass

                    if not link_url or not link_url.startswith("http"):
                        continue

                    if link_url in seen_urls:
                        continue
                    seen_urls.add(link_url)

                    detected_quality = self.detect_quality(link_url)
                    if quality and quality not in detected_quality:
                        continue

                    is_trusted = any(site in link_url for site in self.trusted_sites)
                    results.append({
                        "url": link_url,
                        "title": link.get_text(strip=True) or self.extract_title(link_url, anime_name),
                        "quality": detected_quality,
                        "dubbed": self.detect_dubbed(link_url) or dubbed,
                        "uncensored": self.detect_uncensored(link_url) or uncensored,
                        "source": "duckduckgo_html",
                        "trusted": is_trusted,
                    })

        except Exception as e:
            logger.warning(f"خطا در HTML DuckDuckGo: {e}")

        return results

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

    def detect_quality(self, url: str) -> str:
        url_lower = url.lower()
        if "1080" in url_lower or "1080p" in url_lower:
            return "1080p"
        elif "720" in url_lower or "720p" in url_lower:
            return "720p"
        elif "480" in url_lower or "480p" in url_lower:
            return "480p"
        elif "4k" in url_lower:
            return "4K"
        return "متغیر"

    def detect_dubbed(self, url: str) -> bool:
        url_lower = url.lower()
        keywords = ["دوبله", "dubbed", "dub", "persian", "فارسی", "farsi"]
        return any(keyword in url_lower for keyword in keywords)

    def detect_uncensored(self, url: str) -> bool:
        url_lower = url.lower()
        keywords = ["uncensored", "بدون سانسور", "بی‌سانسور", "without censorship"]
        return any(keyword in url_lower for keyword in keywords)

    def get_anime_details(self, anime_name: str) -> Dict:
        """دریافت اطلاعات کامل انیمه با DeepSeek"""
        if self.deepseek:
            return self.deepseek.get_anime_info(anime_name)
        return None


# ============ کلاس اصلی ربات ============
class AnimeBot:
    def __init__(self, deepseek_client: DeepSeekClient):
        self.searcher = AnimeSearcher(deepseek_client)
        self.deepseek = deepseek_client
        self.user_data: Dict[int, Dict] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data="advanced_search")],
            [InlineKeyboardButton("📂 جستجوی ژانر", callback_data="genres")],
            [InlineKeyboardButton("🤖 جستجوی هوشمند (AI)", callback_data="ai_search")],
            [InlineKeyboardButton("⚙️ فیلترها", callback_data="filters")],
            [InlineKeyboardButton("🏆 محبوب‌ترین‌ها", callback_data="popular")],
            [InlineKeyboardButton("❓ راهنما", callback_data="help")],
        ]

        welcome_text = (
            "🎬 **به ربات جستجوگر انیمه خوش آمدید!**\n\n"
            "✨ **قابلیت‌ها:**\n"
            "• جستجوی هوشمند با هوش مصنوعی DeepSeek 🤖\n"
            "• جستجو در سایت‌های معتبر ایرانی\n"
            "• جستجو در DuckDuckGo\n"
            "• لینک دانلود مستقیم\n"
            "• کیفیت‌های مختلف\n"
            "• تشخیص دوبله و زیرنویس\n"
            "• فیلتر بدون سانسور\n"
            "• جستجوی ژانر\n"
            "• اصلاح املایی هوشمند\n\n"
            "📝 **اسم انیمه رو تایپ کن یا از دکمه‌ها استفاده کن!**"
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

        results = self.searcher.search_google(
            corrected_name, quality=quality, dubbed=dubbed, uncensored=uncensored
        )

        if not results:
            await msg.edit_text(
                f"❌ متأسفم! انیمه «{query_text}» پیدا نشد.\n\n"
                f"💡 **راهکارها:**\n"
                f"• اسم انگلیسی رو امتحان کن\n"
                f"• از جستجوی پیشرفته استفاده کن\n"
                f"• از جستجوی ژانر استفاده کن\n"
                f"• از جستجوی هوشمند (AI) استفاده کن\n\n"
                f"🔄 پیشنهاد: `{corrected_name}`",
                parse_mode="Markdown",
            )
            return

        await self.show_results(msg, corrected_name, results, user_id)

    async def show_results(self, msg, anime_name: str, results: List[Dict], user_id: int):
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id]["results"] = results

        result_text = f"🎯 **نتایج جستجوی «{anime_name}»**\n"
        result_text += f"🔎 {len(results)} نتیجه پیدا شد\n\n"

        display_results = results[:5]

        for i, result in enumerate(display_results, 1):
            quality_icons = {"1080p": "📺", "720p": "💻", "480p": "📱", "4K": "🖥️", "متغیر": "📹"}
            quality_icon = quality_icons.get(result["quality"], "📹")

            dub_text = "🎙️ دوبله فارسی" if result["dubbed"] else "📝 زیرنویس"
            censored_text = "🔞 بدون سانسور" if result["uncensored"] else "✅ سانسور شده"
            trusted_icon = "⭐" if result.get("trusted", False) else ""
            source_text = f"📌 منبع: {result.get('source', 'ناشناس')}"

            result_text += f"{i}. {quality_icon} **{result['title']}** {trusted_icon}\n"
            result_text += f"   📥 کیفیت: {result['quality']}\n"
            result_text += f"   {dub_text}\n"
            result_text += f"   {censored_text}\n"
            result_text += f"   {source_text}\n"
            result_text += f"   🔗 [لینک دانلود]({result['url']})\n\n"
            
            # نمایش اطلاعات اضافی از DeepSeek
            if result.get("extra_info"):
                extra = result["extra_info"]
                if extra.get("summary"):
                    result_text += f"   📝 {extra['summary'][:100]}...\n\n"

        keyboard = []
        for i in range(min(5, len(display_results))):
            quality = display_results[i]["quality"]
            keyboard.append([
                InlineKeyboardButton(
                    f"📥 دانلود گزینه {i+1} ({quality})",
                    callback_data=f"download_{i}",
                )
            ])

        # دکمه اطلاعات کامل (اگر DeepSeek فعال باشد)
        if self.deepseek:
            keyboard.append([
                InlineKeyboardButton("🤖 اطلاعات کامل با AI", callback_data=f"ai_info_{anime_name}")
            ])

        keyboard.append([InlineKeyboardButton("🔄 جستجوی جدید", callback_data="new_search")])
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")])

        await msg.edit_text(
            result_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

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
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
                ])
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
        elif data == "ai_search":
            await self.show_ai_search(query)
        elif data == "new_search":
            await query.edit_message_text("🔍 اسم انیمه مورد نظر رو تایپ کن:")
        elif data.startswith("genre_"):
            genre = data.replace("genre_", "")
            await self.search_by_genre(query, genre)
        elif data.startswith("download_"):
            await self.download_file(query, user_id)
        elif data.startswith("ai_info_"):
            anime_name = data.replace("ai_info_", "")
            await self.get_ai_info(query, anime_name)
        elif data == "filter_dubbed":
            await self.apply_filter(query, user_id, "dubbed")
        elif data == "filter_1080":
            await self.apply_filter(query, user_id, "1080p")
        elif data == "filter_720":
            await self.apply_filter(query, user_id, "720p")
        elif data == "filter_uncensored":
            await self.apply_filter(query, user_id, "uncensored")

    async def show_ai_search(self, query):
        await query.edit_message_text(
            "🤖 **جستجوی هوشمند با هوش مصنوعی**\n\n"
            "اسم انیمه مورد نظر رو تایپ کن تا با استفاده از DeepSeek AI اطلاعات کامل دریافت کنی.\n"
            "مثال: `Attack on Titan`\n\n"
            "✨ **قابلیت‌های جستجوی هوشمند:**\n"
            "• اطلاعات کامل انیمه\n"
            "• خلاصه داستان\n"
            "• ژانرها و سال انتشار\n"
            "• امتیاز و نظرات\n"
            "• لینک‌های دانلود معتبر"
        )

    async def get_ai_info(self, query, anime_name: str):
        await query.edit_message_text(
            f"🤖 در حال دریافت اطلاعات کامل «{anime_name}» از DeepSeek AI...\n⏳ لطفاً صبر کنید..."
        )
        
        info = self.searcher.get_anime_details(anime_name)
        
        if info:
            text = f"📚 **اطلاعات کامل انیمه «{anime_name}»**\n\n"
            text += f"🎬 نام: {info.get('title', anime_name)}\n"
            text += f"🇯🇵 نام ژاپنی: {info.get('نام ژاپنی', 'نامشخص')}\n"
            text += f"📂 ژانرها: {info.get('ژانرها', 'نامشخص')}\n"
            text += f"📖 خلاصه: {info.get('خلاصه داستان', 'نامشخص')}\n"
            text += f"🎞️ تعداد قسمت‌ها: {info.get('تعداد قسمت‌ها', 'نامشخص')}\n"
            text += f"📅 سال انتشار: {info.get('سال انتشار', 'نامشخص')}\n"
            text += f"⭐ امتیاز: {info.get('امتیاز', 'نامشخص')}\n"
            text += f"🏢 استودیو: {info.get('استودیو سازنده', 'نامشخص')}\n"
            text += f"🎬 کارگردان: {info.get('کارگردان', 'نامشخص')}\n"
            text += f"📌 وضعیت: {info.get('وضعیت', 'نامشخص')}\n"
            
            if info.get('لینک‌های دانلود معتبر'):
                text += "\n🔗 **لینک‌های دانلود:**\n"
                for link in info['لینک‌های دانلود معتبر'][:3]:
                    text += f"• {link}\n"
            
            keyboard = [
                [InlineKeyboardButton("🔍 جستجوی جدید", callback_data="new_search")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            await query.edit_message_text(
                f"❌ متأسفم! اطلاعاتی برای «{anime_name}» پیدا نشد.\n"
                f"💡 سعی کن با اسم انگلیسی دقیق‌تر جستجو کنی.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 تلاش مجدد", callback_data="ai_search")],
                    [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
                ])
            )

    async def show_main_menu(self, query):
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data="simple_search")],
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data="advanced_search")],
            [InlineKeyboardButton("📂 جستجوی ژانر", callback_data="genres")],
            [InlineKeyboardButton("🤖 جستجوی هوشمند (AI)", callback_data="ai_search")],
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
            [InlineKeyboardButton("🤖 جستجوی هوشمند", callback_data="ai_search")],
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
        genre_names = self.searcher.genres.get(genre, [genre])
        genre_name = genre_names[0] if genre_names else genre

        await query.edit_message_text(
            f"🔍 در حال جستجوی انیمه‌های ژانر «{genre_name}»...\n⏳ لطفاً صبر کنید..."
        )

        results = self.searcher.search_google(genre_name)

        if results:
            await self.show_results(query.message, f"ژانر {genre_name}", results, query.from_user.id)
        else:
            await query.edit_message_text(
                f"❌ متأسفم! انیمه‌ای با ژانر «{genre_name}» پیدا نشد.\n"
                f"🔄 ژانر دیگری را امتحان کن یا از جستجوی هوشمند استفاده کن.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🤖 جستجوی هوشمند", callback_data="ai_search")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="genres")],
                ])
            )

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
        text += "\n📝 یکی از اسم‌ها رو کپی کن و در چت ارسال کن تا برات جستجو کنم.\n"
        text += "🤖 یا از جستجوی هوشمند برای اطلاعات کامل استفاده کن."

        keyboard = [
            [InlineKeyboardButton("🤖 جستجوی هوشمند", callback_data="ai_search")],
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
            "🔍 جستجوی ساده:\n"
            "• فقط اسم انیمه رو تایپ کن (ترجیحاً انگلیسی)\n\n"
            "🤖 جستجوی هوشمند (AI):\n"
            "• دریافت اطلاعات کامل انیمه\n"
            "• خلاصه داستان و ژانرها\n"
            "• امتیاز و نظرات\n"
            "• لینک‌های دانلود معتبر\n\n"
            "🎯 جستجوی پیشرفته:\n"
            "• فیلتر دوبله فارسی\n"
            "• فیلتر کیفیت 1080p و 720p\n"
            "• فیلتر بدون سانسور\n\n"
            "📂 جستجوی ژانر:\n"
            "• انتخاب ژانر مثل اکشن، کمدی، درام و...\n\n"
            "🏆 محبوب‌ترین‌ها:\n"
            "• نمایش لیست انیمه‌های معروف برای شروع\n\n"
            "اگر نتیجه‌ای پیدا نشد، از جستجوی هوشمند استفاده کن."
        )

        keyboard = [
            [InlineKeyboardButton("🤖 جستجوی هوشمند", callback_data="ai_search")],
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
            [InlineKeyboardButton("🤖 جستجوی هوشمند", callback_data="ai_search")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="advanced_search")],
        ]

        await query.edit_message_text(
            status,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def download_file(self, query, user_id: int):
        if user_id not in self.user_data or "results" not in self.user_data[user_id]:
            await query.edit_message_text(
                "❌ هیچ نتیجه‌ای برای دانلود موجود نیست.\n"
                "🔍 اول یک جستجو انجام بده.",
                parse_mode="Markdown",
            )
            return

        try:
            index = int(query.data.split("_")[1])
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

        # اگر اطلاعات اضافی از DeepSeek وجود دارد
        if result.get("extra_info"):
            extra = result["extra_info"]
            if extra.get("summary"):
                text += f"\n📝 {extra['summary'][:150]}...\n"
            if extra.get("rating"):
                text += f"⭐ امتیاز: {extra['rating']}\n"

        keyboard = [
            [InlineKeyboardButton("🤖 اطلاعات کامل", callback_data=f"ai_info_{result['title']}")],
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


# ============ تابع اصلی اجرای ربات ============
async def run_bot():
    # ایجاد کلاینت DeepSeek
    deepseek_client = DeepSeekClient(DEEPSEEK_API_KEY) if DEEPSEEK_API_KEY else None
    
    if deepseek_client:
        logger.info("🤖 DeepSeek AI فعال شد!")
    else:
        logger.warning("⚠️ DeepSeek AI غیرفعال است - API Key موجود نیست")
    
    bot = AnimeBot(deepseek_client)
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

    logger.info("🤖 ربات انیمه با DeepSeek AI راه‌اندازی شد!")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 در حال توقف ربات...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


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

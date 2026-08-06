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
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs

# ============ تنظیمات ============
TOKEN = "8876632730:AAEplhdqqb24CPLWe6BzF0QIvMuwboQpLNI"

# ============ لاگینگ ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ کلاس جستجوگر ============
class AnimeSearcher:
    def __init__(self):
        self.genres = {
            'action': ['🔥 اکشن', 'مبارزه‌ای', 'جنگی'],
            'adventure': ['🗺️ ماجراجویی', 'سفر', 'اکتشاف'],
            'comedy': ['😂 کمدی', 'طنز', 'خنده‌دار'],
            'drama': ['🎭 درام', 'احساسی', 'غمگین'],
            'fantasy': ['🧙 فانتزی', 'جادویی', 'افسانه‌ای'],
            'horror': ['👻 ترسناک', 'وحشت', 'خونین'],
            'mystery': ['🔍 معمایی', 'کارآگاهی', 'پلیسی'],
            'romance': ['❤️ عاشقانه', 'رمانتیک', 'دل‌بر'],
            'sci_fi': ['🚀 علمی تخیلی', 'فضایی', 'رباتی'],
            'slice_of_life': ['📖 زندگی روزمره', 'اجتماعی', 'واقعی'],
            'sports': ['⚽ ورزشی', 'مسابقه‌ای', 'رقابتی'],
            'supernatural': ['👹 ماورایی', 'فراطبیعی', 'شبح'],
            'psychological': ['🧠 روانشناختی', 'ذهنی', 'پیچیده'],
            'thriller': ['😱 هیجانی', 'مهیج', 'پرتنش']
        }
        
        self.popular_anime = [
            'naruto', 'one piece', 'bleach', 'attack on titan', 'demon slayer',
            'jujutsu kaisen', 'my hero academia', 'death note', 'fullmetal alchemist',
            'dragon ball', 'pokemon', 'sailor moon', 'hunter x hunter', 'one punch man',
            'tokyo ghoul', 'sword art online', 'fairy tail', 'gintama', 'jojo bizarre',
            'spy x family', 'chainsaw man', 'vinland saga', 'berserk', 'evangelion'
        ]
        
        self.trusted_sites = [
            'animekhor.ir', 'animelab.ir', 'animeshow.ir',
            'iran-anime.ir', 'animeworld.ir', 'anime-4u.ir',
            'animefa.ir', 'animedl.ir', 'animecity.ir'
        ]
        
        # Cache برای نتایج جستجو
        self.search_cache = {}
        self.cache_timeout = 600  # 10 دقیقه
        
        # لیست User-Agent های مختلف
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
        ]
        
        # سایت‌های معتبر ایرانی برای دانلود انیمه
        self.anime_sites = [
            {
                'name': 'AnimeKhor',
                'url': 'https://animekhor.ir',
                'search_url': 'https://animekhor.ir/?s={}'
            },
            {
                'name': 'AnimeLab',
                'url': 'https://animelab.ir',
                'search_url': 'https://animelab.ir/?s={}'
            },
            {
                'name': 'AnimeShow',
                'url': 'https://animeshow.ir',
                'search_url': 'https://animeshow.ir/?s={}'
            },
            {
                'name': 'IranAnime',
                'url': 'https://iran-anime.ir',
                'search_url': 'https://iran-anime.ir/?s={}'
            },
            {
                'name': 'AnimeWorld',
                'url': 'https://animeworld.ir',
                'search_url': 'https://animeworld.ir/?s={}'
            }
        ]
    
    def correct_spelling(self, name: str) -> str:
        from difflib import get_close_matches
        name = name.lower().strip()
        if len(name) < 2:
            return name
        matches = get_close_matches(name, self.popular_anime, n=1, cutoff=0.6)
        return matches[0] if matches else name
    
    def _get_cache_key(self, anime_name: str, quality: str = None, dubbed: bool = False, 
                      uncensored: bool = False) -> str:
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
    
    def search_google(self, anime_name: str, quality: str = None, dubbed: bool = False, 
                      uncensored: bool = False) -> List[Dict]:
        cache_key = self._get_cache_key(anime_name, quality, dubbed, uncensored)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        results = []
        
        # روش 1: جستجو در سایت‌های معتبر ایرانی
        logger.info(f"🔍 جستجو در سایت‌های معتبر برای: {anime_name}")
        results = self._search_trusted_sites(anime_name, quality, dubbed, uncensored)
        
        # روش 2: اگر نتیجه‌ای نداشت، از DuckDuckGo استفاده کن
        if not results:
            logger.info("🔄 استفاده از DuckDuckGo به عنوان جایگزین")
            query = f'"{anime_name}" انیمه دانلود لینک مستقیم'
            if quality:
                query += f" {quality}"
            if dubbed:
                query += " دوبله فارسی"
            if uncensored:
                query += " بدون سانسور"
            results = self._duckduckgo_search(query, anime_name, quality, dubbed, uncensored)
        
        # روش 3: جستجو در سایت‌های معروف انیمه با استفاده از گوگل (با تاخیر بیشتر)
        if not results:
            logger.info("🔄 جستجو در سایت‌های معروف انیمه")
            results = self._search_anime_sites(anime_name, quality, dubbed, uncensored)
        
        # روش 4: استفاده از Bing (از طریق DuckDuckGo)
        if not results:
            logger.info("🔄 جستجو در Bing از طریق DuckDuckGo")
            query = f'{anime_name} anime download'
            results = self._duckduckgo_search(query, anime_name, quality, dubbed, uncensored)
        
        # مرتب‌سازی نتایج
        results.sort(key=lambda x: (not x['trusted'], x['quality'] != '1080p'))
        
        # ذخیره در کش
        if results:
            self._save_to_cache(cache_key, results[:10])
        
        return results[:10]
    
    def _search_trusted_sites(self, anime_name: str, quality: str = None,
                              dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        """جستجو مستقیم در سایت‌های معتبر ایرانی"""
        results = []
        seen_urls = set()
        
        for site in self.anime_sites:
            try:
                search_url = site['search_url'].format(quote_plus(anime_name))
                headers = {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7'
                }
                
                time.sleep(random.uniform(1, 2))
                response = requests.get(search_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # پیدا کردن لینک‌های مقاله
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        # فیلتر لینک‌های مفید
                        if href and ('anime' in href.lower() or 'دانلود' in href):
                            if href.startswith('/'):
                                href = site['url'] + href
                            
                            if href in seen_urls:
                                continue
                            seen_urls.add(href)
                            
                            # بررسی کیفیت
                            detected_quality = self.detect_quality(href)
                            if quality and quality not in detected_quality:
                                continue
                            
                            is_trusted = True
                            results.append({
                                'url': href,
                                'title': title or self.extract_title(href, anime_name),
                                'quality': detected_quality,
                                'dubbed': self.detect_dubbed(href) or dubbed,
                                'uncensored': self.detect_uncensored(href) or uncensored,
                                'source': site['name'],
                                'trusted': is_trusted
                            })
                            
                            if len(results) >= 5:
                                break
                            
            except Exception as e:
                logger.warning(f"خطا در جستجوی {site['name']}: {e}")
                continue
        
        return results
    
    def _search_anime_sites(self, anime_name: str, quality: str = None,
                            dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        """جستجو در سایت‌های معروف انیمه با استفاده از گوگل (با تاخیر بیشتر)"""
        results = []
        seen_urls = set()
        
        try:
            # ساخت query برای سایت‌های معروف
            site_queries = [
                f'site:animekhor.ir {anime_name}',
                f'site:animelab.ir {anime_name}',
                f'site:animeshow.ir {anime_name}',
                f'site:iran-anime.ir {anime_name}'
            ]
            
            for site_query in site_queries:
                try:
                    time.sleep(random.uniform(3, 5))  # تاخیر بیشتر
                    
                    # استفاده از DuckDuckGo برای جستجو
                    url = "https://html.duckduckgo.com/html/"
                    params = {"q": site_query}
                    headers = {
                        'User-Agent': random.choice(self.user_agents)
                    }
                    
                    response = requests.get(url, params=params, headers=headers, timeout=20)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        for link in soup.select('a.result__a')[:5]:
                            href = link.get('href', '')
                            if href and 'http' in href:
                                if href in seen_urls:
                                    continue
                                seen_urls.add(href)
                                
                                is_trusted = any(site in href for site in self.trusted_sites)
                                results.append({
                                    'url': href,
                                    'title': link.get_text(strip=True) or self.extract_title(href, anime_name),
                                    'quality': self.detect_quality(href),
                                    'dubbed': self.detect_dubbed(href) or dubbed,
                                    'uncensored': self.detect_uncensored(href) or uncensored,
                                    'source': 'anime_site_search',
                                    'trusted': is_trusted
                                })
                                
                except Exception as e:
                    logger.warning(f"خطا در جستجوی {site_query}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"خطا در جستجوی سایت‌های انیمه: {e}")
        
        return results
    
    def _duckduckgo_search(self, query: str, anime_name: str, quality: str = None,
                           dubbed: bool = False, uncensored: bool = False) -> List[Dict]:
        """جستجو از طریق DuckDuckGo HTML"""
        results = []
        seen_urls = set()
        
        for attempt in range(3):
            try:
                logger.info(f"جستجوی DuckDuckGo: {query} (تلاش {attempt+1})")
                url = "https://html.duckduckgo.com/html/"
                params = {"q": query}
                
                headers = {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                # تاخیر تصادفی
                time.sleep(random.uniform(2, 4))
                
                response = requests.get(url, params=params, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.select('a.result__a')[:15]:
                        link_url = link.get('href', '')
                        
                        # استخراج URL واقعی از redirect DuckDuckGo
                        if link_url and link_url.startswith('//duckduckgo.com/l/'):
                            try:
                                parsed = urlparse(link_url)
                                query_params = parse_qs(parsed.query)
                                if 'uddg' in query_params:
                                    import urllib.parse
                                    uddg = query_params['uddg'][0]
                                    decoded = urllib.parse.unquote(uddg)
                                    if 'http' in decoded:
                                        link_url = decoded.split('http')[1]
                                        link_url = 'http' + link_url
                                        if '&' in link_url:
                                            link_url = link_url.split('&')[0]
                            except Exception:
                                pass
                        
                        if not link_url or not link_url.startswith('http'):
                            continue
                        
                        if link_url in seen_urls:
                            continue
                        seen_urls.add(link_url)
                        
                        # بررسی کیفیت
                        detected_quality = self.detect_quality(link_url)
                        if quality and quality not in detected_quality:
                            continue
                        
                        is_trusted = any(site in link_url for site in self.trusted_sites)
                        results.append({
                            'url': link_url,
                            'title': link.get_text(strip=True) or self.extract_title(link_url, anime_name),
                            'quality': detected_quality,
                            'dubbed': self.detect_dubbed(link_url) or dubbed,
                            'uncensored': self.detect_uncensored(link_url) or uncensored,
                            'source': 'duckduckgo',
                            'trusted': is_trusted
                        })
                    
                    if results:
                        break
                else:
                    logger.warning(f"DuckDuckGo status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Timeout در DuckDuckGo (تلاش {attempt+1})")
                time.sleep(5)
            except Exception as e:
                logger.warning(f"خطا در DuckDuckGo (تلاش {attempt+1}): {e}")
                time.sleep(3)
        
        return results
    
    def extract_title(self, url: str, default_name: str) -> str:
        try:
            # استخراج از URL
            url_parts = url.split('/')
            for part in url_parts:
                if any(anime in part.lower() for anime in self.popular_anime):
                    title = part.replace('-', ' ').replace('_', ' ').replace('%20', ' ').title()
                    if len(title) > 3:
                        return title
            return default_name.title()
        except Exception:
            return default_name.title()
    
    def detect_quality(self, url: str) -> str:
        url_lower = url.lower()
        if '1080' in url_lower or '1080p' in url_lower:
            return '1080p'
        elif '720' in url_lower or '720p' in url_lower:
            return '720p'
        elif '480' in url_lower or '480p' in url_lower:
            return '480p'
        elif '4k' in url_lower:
            return '4K'
        return 'متغیر'
    
    def detect_dubbed(self, url: str) -> bool:
        url_lower = url.lower()
        keywords = ['دوبله', 'dubbed', 'dub', 'persian', 'فارسی', 'farsi']
        return any(keyword in url_lower for keyword in keywords)
    
    def detect_uncensored(self, url: str) -> bool:
        url_lower = url.lower()
        keywords = ['uncensored', 'بدون سانسور', 'بی‌سانسور', 'without censorship']
        return any(keyword in url_lower for keyword in keywords)

# ============ کلاس اصلی ربات ============
class AnimeBot:
    def __init__(self):
        self.searcher = AnimeSearcher()
        self.user_data = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data='simple_search')],
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data='advanced_search')],
            [InlineKeyboardButton("📂 جستجوی ژانر", callback_data='genres')],
            [InlineKeyboardButton("⚙️ فیلترها", callback_data='filters')],
            [InlineKeyboardButton("🏆 محبوب‌ترین‌ها", callback_data='popular')],
            [InlineKeyboardButton("❓ راهنما", callback_data='help')]
        ]
        
        welcome_text = (
            "🎬 **به ربات جستجوگر انیمه خوش آمدید!**\n\n"
            "✨ **قابلیت‌ها:**\n"
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
            parse_mode='Markdown'
        )
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.message.text.strip()
        user_id = update.effective_user.id
        
        if not query or len(query) < 2:
            await update.message.reply_text(
                "❌ لطفاً اسم انیمه رو درست وارد کن!\nمثال: `Attack on Titan`",
                parse_mode='Markdown'
            )
            return
        
        msg = await update.message.reply_text(
            f"🔍 در حال جستجوی «{query}»...\n⏳ لطفاً چند لحظه صبر کنید...",
            parse_mode='Markdown'
        )
        
        corrected_name = self.searcher.correct_spelling(query)
        
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id]['last_search'] = corrected_name
        
        results = self.searcher.search_google(corrected_name)
        
        if not results:
            await msg.edit_text(
                f"❌ متأسفم! انیمه «{query}» پیدا نشد.\n\n"
                f"💡 **راهکارها:**\n"
                f"• اسم انگلیسی رو امتحان کن\n"
                f"• از جستجوی پیشرفته استفاده کن\n"
                f"• از جستجوی ژانر استفاده کن\n\n"
                f"🔄 پیشنهاد: `{corrected_name}`",
                parse_mode='Markdown'
            )
            return
        
        await self.show_results(msg, corrected_name, results, user_id)
    
    async def show_results(self, msg, anime_name: str, results: List[Dict], user_id: int):
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id]['results'] = results
        
        result_text = f"🎯 **نتایج جستجوی «{anime_name}»**\n"
        result_text += f"🔎 {len(results)} نتیجه پیدا شد\n\n"
        
        display_results = results[:5]
        
        for i, result in enumerate(display_results, 1):
            quality_icons = {'1080p': '📺', '720p': '💻', '480p': '📱', '4K': '🖥️', 'متغیر': '📹'}
            quality_icon = quality_icons.get(result['quality'], '📹')
            
            dub_text = "🎙️ دوبله فارسی" if result['dubbed'] else "📝 زیرنویس"
            censored_text = "🔞 بدون سانسور" if result['uncensored'] else "✅ سانسور شده"
            trusted_icon = "⭐" if result.get('trusted', False) else ""
            source_text = f"📌 منبع: {result.get('source', 'ناشناس')}"
            
            result_text += f"{i}. {quality_icon} **{result['title']}** {trusted_icon}\n"
            result_text += f"   📥 کیفیت: {result['quality']}\n"
            result_text += f"   {dub_text}\n"
            result_text += f"   {censored_text}\n"
            result_text += f"   {source_text}\n"
            result_text += f"   🔗 [لینک دانلود]({result['url']})\n\n"
        
        keyboard = []
        for i in range(min(5, len(display_results))):
            quality = display_results[i]['quality']
            keyboard.append([InlineKeyboardButton(
                f"📥 دانلود گزینه {i+1} ({quality})",
                callback_data=f'download_{i}'
            )])
        
        keyboard.append([InlineKeyboardButton("🔄 جستجوی جدید", callback_data='new_search')])
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')])
        
        await msg.edit_text(
            result_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data == 'main_menu':
            await self.show_main_menu(query)
        elif data == 'simple_search':
            await query.edit_message_text(
                "🔍 **جستجوی ساده**\n\nاسم انیمه مورد نظر رو تایپ کن.\nمثال: `Naruto`",
                parse_mode='Markdown'
            )
        elif data == 'advanced_search':
            await self.show_advanced_search(query)
        elif data == 'genres':
            await self.show_genres(query)
        elif data == 'filters':
            await self.show_filters(query)
        elif data == 'popular':
            await self.show_popular(query)
        elif data == 'help':
            await self.show_help(query)
        elif data == 'new_search':
            await query.edit_message_text("🔍 اسم انیمه مورد نظر رو تایپ کن:")
        elif data.startswith('genre_'):
            genre = data.replace('genre_', '')
            await self.search_by_genre(query, genre)
        elif data.startswith('download_'):
            await self.download_file(query, user_id)
        elif data == 'filter_dubbed':
            await self.apply_filter(query, user_id, 'dubbed')
        elif data == 'filter_1080':
            await self.apply_filter(query, user_id, '1080p')
        elif data == 'filter_720':
            await self.apply_filter(query, user_id, '720p')
        elif data == 'filter_uncensored':
            await self.apply_filter(query, user_id, 'uncensored')
    
    async def show_main_menu(self, query):
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی ساده", callback_data='simple_search')],
            [InlineKeyboardButton("🎯 جستجوی پیشرفته", callback_data='advanced_search')],
            [InlineKeyboardButton("📂 جستجوی ژانر", callback_data='genres')],
            [InlineKeyboardButton("⚙️ فیلترها", callback_data='filters')],
            [InlineKeyboardButton("🏆 محبوب‌ترین‌ها", callback_data='popular')],
            [InlineKeyboardButton("❓ راهنما", callback_data='help')]
        ]
        
        await query.edit_message_text(
            "🎬 **منوی اصلی**\n\nیکی از گزینه‌های زیر رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_advanced_search(self, query):
        keyboard = [
            [InlineKeyboardButton("🎙️ دوبله فارسی", callback_data='filter_dubbed')],
            [InlineKeyboardButton("📺 کیفیت 1080p", callback_data='filter_1080')],
            [InlineKeyboardButton("📺 کیفیت 720p", callback_data='filter_720')],
            [InlineKeyboardButton("🚫 بدون سانسور", callback_data='filter_uncensored')],
            [InlineKeyboardButton("🔍 شروع جستجو", callback_data='simple_search')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            "🎯 **جستجوی پیشرفته**\n\nفیلترهای مورد نظر رو انتخاب کن، سپس روی «شروع جستجو» بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_genres(self, query):
        keyboard = []
        for genre_en, genre_list in self.searcher.genres.items():
            display_name = genre_list[0] if genre_list else genre_en
            keyboard.append([InlineKeyboardButton(display_name, callback_data=f'genre_{genre_en}')])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')])
        
        await query.edit_message_text(
            "🎬 **انتخاب ژانر**\n\nژانر مورد نظر رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
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
                f"❌ متأسفم! انیمه‌ای در ژانر «{genre_name}» پیدا نشد.",
                parse_mode='Markdown'
            )
    
    async def show_filters(self, query):
        keyboard = [
            [InlineKeyboardButton("🎙️ دوبله فارسی", callback_data='filter_dubbed')],
            [InlineKeyboardButton("📝 زیرنویس", callback_data='filter_sub')],
            [InlineKeyboardButton("📺 کیفیت 1080p", callback_data='filter_1080')],
            [InlineKeyboardButton("📺 کیفیت 720p", callback_data='filter_720')],
            [InlineKeyboardButton("🚫 بدون سانسور", callback_data='filter_uncensored')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            "⚙️ **تنظیمات فیلتر**\n\nبا انتخاب هر گزینه، نتایج جستجو فیلتر میشن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def apply_filter(self, query, user_id: int, filter_type: str):
        await query.answer(f"فیلتر {filter_type} اعمال شد!")
        
        user_data = self.user_data.get(user_id, {})
        results = user_data.get('results', [])
        
        if not results:
            await query.edit_message_text(
                "❌ ابتدا یک جستجو انجام بده!",
                parse_mode='Markdown'
            )
            return
        
        filtered_results = []
        for result in results:
            if filter_type == 'dubbed' and not result.get('dubbed', False):
                continue
            elif filter_type == '1080p' and result.get('quality', '') != '1080p':
                continue
            elif filter_type == '720p' and result.get('quality', '') != '720p':
                continue
            elif filter_type == 'uncensored' and not result.get('uncensored', False):
                continue
            filtered_results.append(result)
        
        if not filtered_results:
            await query.edit_message_text(
                f"❌ با فیلتر انتخاب شده نتیجه‌ای پیدا نشد.",
                parse_mode='Markdown'
            )
            return
        
        await self.show_results(query.message, "نتایج فیلتر شده", filtered_results, user_id)
    
    async def show_popular(self, query):
        popular_list = [
            ("🔥 Attack on Titan", "https://animekhor.ir/attack-on-titan"),
            ("⚡ Demon Slayer", "https://animekhor.ir/demon-slayer"),
            ("👊 Jujutsu Kaisen", "https://animekhor.ir/jujutsu-kaisen"),
            ("🏴‍☠️ One Piece", "https://animekhor.ir/one-piece"),
            ("🍥 Naruto", "https://animekhor.ir/naruto"),
            ("💀 Death Note", "https://animekhor.ir/death-note")
        ]
        
        text = "🏆 **محبوب‌ترین انیمه‌ها**\n\n"
        for i, (name, _) in enumerate(popular_list, 1):
            text += f"{i}. {name}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_help(self, query):
        help_text = (
            "❓ **راهنمای ربات**\n\n"
            "🎯 **چطور استفاده کنم؟**\n"
            "1. اسم انیمه رو تایپ کن\n"
            "2. یا از دکمه‌های منو استفاده کن\n\n"
            "🔍 **قابلیت‌ها:**\n"
            "• جستجوی ساده: فقط اسم رو بنویس\n"
            "• جستجوی پیشرفته: با فیلترهای مختلف\n"
            "• جستجوی ژانر: بر اساس دسته‌بندی\n"
            "• فیلترها: دوبله، کیفیت، سانسور\n\n"
            "📌 **نکته:** برای بهترین نتیجه، اسم انگلیسی رو بنویس."
        )
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]]
        
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def download_file(self, query, user_id: int):
        user_data = self.user_data.get(user_id, {})
        results = user_data.get('results', [])
        
        try:
            index = int(query.data.replace('download_', ''))
            if index < len(results):
                selected = results[index]
                url = selected.get('url', '')
                title = selected.get('title', '')
                quality = selected.get('quality', '')
                
                download_text = (
                    f"📥 **لینک دانلود**\n\n"
                    f"🎬 {title}\n"
                    f"📺 کیفیت: {quality}\n\n"
                    f"🔗 {url}\n\n"
                    f"💡 لینک رو کپی کن و در مرورگر باز کن"
                )
                
                keyboard = [
                    [InlineKeyboardButton("🔄 جستجوی جدید", callback_data='new_search')],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
                ]
                
                await query.edit_message_text(
                    download_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text("❌ گزینه مورد نظر پیدا نشد!", parse_mode='Markdown')
        except (ValueError, IndexError):
            await query.edit_message_text("❌ خطا در دانلود!", parse_mode='Markdown')

# ============ سرور سلامت ============
class HealthHandler(BaseHTTPRequestHandler):
    """شناخته‌سازی سلامت برای Render تا سرویس پایدار و تک‌نمونه بماند."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        try:
            self.wfile.write(b"ok")
        except Exception:
            pass

    def log_message(self, format, *args):
        return


def start_health_server():
    """سرور HTTP کوچک روی PORT برای رفع مشکل 'No open ports' در Render."""
    port = int(os.getenv("PORT", "8080"))
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        logger.info(f"✅ سرور سلامت روی پورت {port} راه‌اندازی شد.")
    except Exception as e:
        logger.warning(f"⚠️ امکان راه‌اندازی سرور سلامت وجود نداشت: {e}")


async def run_polling_loop(application):
    """حلقه پولینگ دستی که خطای Conflict را مدیریت می‌کند."""
    offset = -1
    consecutive_conflicts = 0

    while True:
        try:
            updates = await application.bot.get_updates(
                offset=offset,
                timeout=15,
                allowed_updates=Update.ALL_TYPES,
            )
            consecutive_conflicts = 0
        except telegram.error.Conflict:
            consecutive_conflicts += 1
            logger.warning(
                f"⚠️ Conflict در getUpdates (جلسهٔ قدیمی فعال است). "
                f"صبر و بازیابی... ({consecutive_conflicts})"
            )
            offset = -1
            await asyncio.sleep(5)
            continue
        except telegram.error.TimedOut:
            logger.warning("⏰ Timeout در getUpdates، تلاش دوباره...")
            await asyncio.sleep(3)
            continue
        except telegram.error.NetworkError as e:
            logger.warning(f"🌐 خطای شبکه: {e}")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در getUpdates: {e}")
            await asyncio.sleep(10)
            continue

        for update in updates:
            offset = update.update_id + 1
            try:
                await application.process_update(update)
            except telegram.error.Conflict:
                logger.warning("⚠️ Conflict هنگام پردازش آپدیت.")
                offset = -1
                break
            except Exception as e:
                logger.error(f"خطا در پردازش آپدیت: {e}")


async def main_async():
    start_health_server()

    while True:
        application = None
        try:
            bot = AnimeBot()
            application = Application.builder().token(TOKEN).build()

            application.add_handler(CommandHandler("start", bot.start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_search))
            application.add_handler(CallbackQueryHandler(bot.handle_callback))

            await application.initialize()
            await application.start()

            logger.info("🤖 ربات انیمه راه‌اندازی شد!")
            await run_polling_loop(application)

        except Exception as e:
            logger.error(f"خطا در راه‌اندازی ربات: {e}")
            await asyncio.sleep(5)
        finally:
            if application is not None:
                try:
                    await application.stop()
                    await application.shutdown()
                except Exception:
                    logger.exception("خطا هنگام توقف application")


def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()

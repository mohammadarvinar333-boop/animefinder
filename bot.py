import os
import re
import json
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from googlesearch import search

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
            'iran-anime.ir', 'animeworld.ir', 'anime-4u.ir'
        ]
    
    def correct_spelling(self, name: str) -> str:
        from difflib import get_close_matches
        name = name.lower().strip()
        if len(name) < 2:
            return name
        matches = get_close_matches(name, self.popular_anime, n=1, cutoff=0.6)
        return matches[0] if matches else name
    
    def search_google(self, anime_name: str, quality: str = None, dubbed: bool = False, 
                      uncensored: bool = False) -> List[Dict]:
        query_parts = [f'"{anime_name}"', 'انیمه', 'دانلود']
        if quality:
            query_parts.append(quality)
        if dubbed:
            query_parts.append('دوبله فارسی')
        if uncensored:
            query_parts.append('بدون سانسور')
        query_parts.append('لینک مستقیم')
        query = ' '.join(query_parts)
        
        results = []
        seen_urls = set()
        
        try:
            logger.info(f"جستجوی گوگل برای: {query}")
            search_results = list(search(query, num=12, lang='fa', stop=12))
            
            for url in search_results:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                is_trusted = any(site in url for site in self.trusted_sites)
                
                result = {
                    'url': url,
                    'title': self.extract_title(url, anime_name),
                    'quality': self.detect_quality(url),
                    'dubbed': self.detect_dubbed(url) or dubbed,
                    'uncensored': self.detect_uncensored(url) or uncensored,
                    'source': 'google',
                    'trusted': is_trusted
                }
                results.append(result)
            
            results.sort(key=lambda x: (not x['trusted'], x['quality'] != '1080p'))
            
        except Exception as e:
            logger.error(f"خطا در جستجوی گوگل: {e}")
        
        return results[:8]
    
    def extract_title(self, url: str, default_name: str) -> str:
        url_parts = url.split('/')
        for part in url_parts:
            if any(anime in part.lower() for anime in self.popular_anime):
                return part.replace('-', ' ').replace('_', ' ').title()
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
        keywords = ['دوبله', 'dubbed', 'dub', 'persian', 'فارسی']
        return any(keyword in url_lower for keyword in keywords)
    
    def detect_uncensored(self, url: str) -> bool:
        url_lower = url.lower()
        keywords = ['uncensored', 'بدون سانسور', 'بی‌سانسور']
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
            "• جستجو در گوگل\n"
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
            
            result_text += f"{i}. {quality_icon} **{result['title']}** {trusted_icon}\n"
            result_text += f"   📥 کیفیت: {result['quality']}\n"
            result_text += f"   {dub_text}\n"
            result_text += f"   {censored_text}\n"
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

# ============ اجرای ربات با مدیریت صحیح Event Loop ============
async def run_bot():
    """تابع اصلی اجرای ربات با مدیریت Event Loop"""
    try:
        bot = AnimeBot()
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_search))
        application.add_handler(CallbackQueryHandler(bot.handle_callback))
        
        logger.info("🤖 ربات انیمه در حال راه‌اندازی...")
        
        # شروع پولینگ با مدیریت صحیح
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("✅ ربات انیمه با موفقیت راه‌اندازی شد!")
        
        # نگه داشتن ربات در حال اجرا
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        raise
    finally:
        if 'application' in locals():
            await application.stop()
            await application.shutdown()

def main():
    """ورودی اصلی برنامه"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 ربات متوقف شد")
    except Exception as e:
        logger.error(f"خطای اصلی: {e}")

if __name__ == "__main__":
    main()

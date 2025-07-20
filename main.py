import telethon
from telethon import TelegramClient, events, functions, types
import asyncio
import re
import random
import time
from datetime import datetime, timedelta
import os
import json
import pytz
import sqlite3
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACCOUNTS = [
    {"name": "session1", "app_id": 24966426, "api_hash": "78cc86a35e99aa707e6456179782641d"},
    {"name": "session2", "app_id": 27180402, "api_hash": "400c3285cd1eb6e8a638b45a90e7cba3"},
    {"name": "session3", "app_id": 29860564, "api_hash": "3e58281c574a1c9abfa8d50cbb55a6df"},
    {"name": "session4", "app_id": "29860564", "api_hash": "3e58281c574a1c9abfa8d50cbb55a6df"},
    {"name": "session5", "app_id": "15992426", "api_hash": "e32ed9721a2d3cddc3c080bd4c9e1346"}
]

OWNER_ID = 819127707

# Database for star collection
STAR_DB_NAME = "telegram_stars.db"

# Star collection keywords
STAR_KEYWORDS = [
    "هدية تليجرام", "جمع النجوم", "هدية بريميوم", "Telegram Premium", "Free Stars",
    "جمع نقاط", "هدية مجانية", "تجميع نجوم", "حصري النجوم", "قناة النجوم",
    "قنوات النجوم", "بوت النجوم", "بريميوم مجاني", "تجميع النقاط", "بوت النقاط"
]

# Global variables
user_ids = {}
reply_tracking = {}
member_stealing = {}
active_stealing_tasks = {}
auto_posting_tasks = {}
auto_reply_settings = {
    'enabled': {},
    'message': {},
    'replied_users': {}
}
media_saving_settings = {}

star_collection = {
    'enabled': {},
    'active_accounts': {},
    'channels': set(),
    'stats': {
        'collected': {},
        'channels_checked': {},
        'last_check': {}
    },
    'delay': 30  # Default delay between operations
}

def init_star_db():
    """Initialize the star collection database"""
    conn = sqlite3.connect(STAR_DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS star_channels
                 (id INTEGER PRIMARY KEY, username TEXT, last_checked TEXT, success_rate REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS star_stats
                 (id INTEGER PRIMARY KEY, account_id INTEGER, date TEXT, stars_collected INTEGER)''')
    conn.commit()
    conn.close()

def load_settings():
    global reply_tracking, member_stealing, auto_reply_settings, media_saving_settings, star_collection
    try:
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                data = json.load(f)
                reply_tracking = data.get('reply_tracking', {})
                member_stealing = data.get('member_stealing', {})
                auto_reply_settings = data.get('auto_reply_settings', {
                    'enabled': {},
                    'message': {},
                    'replied_users': {}
                })
                media_saving_settings = data.get('media_saving_settings', {})
                star_collection = data.get('star_collection', {
                    'enabled': {},
                    'active_accounts': {},
                    'channels': set(),
                    'stats': {
                        'collected': {},
                        'channels_checked': {},
                        'last_check': {}
                    },
                    'delay': 30
                })
                
                # Convert keys to strings for consistency
                reply_tracking = {str(k): v for k, v in reply_tracking.items()}
                member_stealing = {str(k): v for k, v in member_stealing.items()}
                auto_reply_settings['enabled'] = {str(k): v for k, v in auto_reply_settings['enabled'].items()}
                auto_reply_settings['message'] = {str(k): v for k, v in auto_reply_settings['message'].items()}
                auto_reply_settings['replied_users'] = {str(k): set(v) for k, v in auto_reply_settings['replied_users'].items()}
                media_saving_settings = {str(k): v for k, v in media_saving_settings.items()}
                star_collection['enabled'] = {str(k): v for k, v in star_collection.get('enabled', {}).items()}
                star_collection['active_accounts'] = {str(k): v for k, v in star_collection.get('active_accounts', {}).items()}
                star_collection['stats']['collected'] = {str(k): v for k, v in star_collection['stats'].get('collected', {}).items()}
                star_collection['stats']['channels_checked'] = {str(k): v for k, v in star_collection['stats'].get('channels_checked', {}).items()}
                star_collection['stats']['last_check'] = {str(k): v for k, v in star_collection['stats'].get('last_check', {}).items()}
                
                # Load star channels from database
                init_star_db()
                conn = sqlite3.connect(STAR_DB_NAME)
                c = conn.cursor()
                c.execute("SELECT username FROM star_channels WHERE success_rate > 0.3")
                star_collection['channels'] = {row[0] for row in c.fetchall()}
                conn.close()
    except Exception as e:
        print(f"Error loading settings: {e}")
        # Initialize default settings if loading fails
        reply_tracking = {}
        member_stealing = {}
        auto_reply_settings = {
            'enabled': {},
            'message': {},
            'replied_users': {}
        }
        media_saving_settings = {}
        star_collection = {
            'enabled': {},
            'active_accounts': {},
            'channels': set(),
            'stats': {
                'collected': {},
                'channels_checked': {},
                'last_check': {}
            },
            'delay': 30
        }
        init_star_db()

def save_settings():
    try:
        with open('settings.json', 'w') as f:
            json.dump({
                'reply_tracking': reply_tracking,
                'member_stealing': member_stealing,
                'auto_reply_settings': {
                    'enabled': auto_reply_settings['enabled'],
                    'message': auto_reply_settings['message'],
                    'replied_users': {k: list(v) for k, v in auto_reply_settings['replied_users'].items()}
                },
                'media_saving_settings': media_saving_settings,
                'star_collection': {
                    'enabled': star_collection['enabled'],
                    'active_accounts': star_collection['active_accounts'],
                    'channels': list(star_collection['channels']),
                    'stats': {
                        'collected': star_collection['stats']['collected'],
                        'channels_checked': star_collection['stats']['channels_checked'],
                        'last_check': star_collection['stats']['last_check']
                    },
                    'delay': star_collection['delay']
                }
            }, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

clients = [TelegramClient(acc["name"], acc["app_id"], acc["api_hash"]) for acc in ACCOUNTS]

async def start_all_clients():
    for i, client in enumerate(clients, 1):
        try:
            await client.start()
            print(f"Account {i} started successfully")
        except Exception as e:
            print(f"Error starting account {i}: {e}")

async def get_user_ids():
    global user_ids
    for i, client in enumerate(clients, 1):
        try:
            me = await client.get_me()
            user_ids[i] = me.id
            print(f"User ID for account {i}: {me.id}")
        except Exception as e:
            print(f"Error getting user ID for account {i}: {e}")

def extract_entity_id(peer):
    if isinstance(peer, str):
        if peer.startswith('https://t.me/'):
            peer = peer.split('/')[-1]
        if peer.startswith('+') or peer.startswith('@'):
            return peer
        try:
            return int(peer)
        except ValueError:
            return peer
    return peer

async def get_channel_limit(client, channel):
    try:
        full_channel = await client(functions.channels.GetFullChannelRequest(channel))
        return {
            'current': full_channel.full_chat.participants_count,
            'limit': full_channel.full_chat.participants_count if hasattr(full_channel.full_chat, 'participants_limit') else 200000
        }
    except Exception as e:
        print(f"Error getting channel info: {e}")
        return {'current': 0, 'limit': 200000}

async def steal_members(client, account_num, source, destination):
    try:
        if active_stealing_tasks.get(account_num, False):
            await client.send_message("me", f"Active stealing process already running for account {account_num}")
            return

        active_stealing_tasks[account_num] = True
        member_stealing[str(account_num)] = True
        save_settings()

        try:
            source_entity = await client.get_entity(extract_entity_id(source))
        except Exception as e:
            print(f"Error getting source entity: {str(e)}")
            await client.send_message("me", f"Error getting source entity: {str(e)}")
            active_stealing_tasks[account_num] = False
            member_stealing[str(account_num)] = False
            save_settings()
            return

        try:
            dest_entity = await client.get_entity(extract_entity_id(destination))
        except Exception as e:
            print(f"Error getting destination entity: {str(e)}")
            await client.send_message("me", f"Error getting destination entity: {str(e)}")
            active_stealing_tasks[account_num] = False
            member_stealing[str(account_num)] = False
            save_settings()
            return
        
        try:
            dest_info = await get_channel_limit(client, dest_entity)
        except Exception as e:
            print(f"Error getting channel limit: {str(e)}")
            await client.send_message("me", f"Error getting channel limit: {str(e)}")
            active_stealing_tasks[account_num] = False
            member_stealing[str(account_num)] = False
            save_settings()
            return
        
        remaining_slots = dest_info['limit'] - dest_info['current']
        
        if remaining_slots <= 0:
            await client.send_message("me", f"Target channel has reached maximum members ({dest_info['limit']})")
            active_stealing_tasks[account_num] = False
            member_stealing[str(account_num)] = False
            save_settings()
            return
        
        try:
            members = await client.get_participants(source_entity, aggressive=True)
        except Exception as e:
            print(f"Error getting participants: {str(e)}")
            await client.send_message("me", f"Error getting participants: {str(e)}")
            active_stealing_tasks[account_num] = False
            member_stealing[str(account_num)] = False
            save_settings()
            return
        
        total_members = len(members)
        
        start_msg = (
            f"Starting member transfer from {getattr(source_entity, 'title', 'Unknown')} to {getattr(dest_entity, 'title', 'Unknown')}\n\n"
            f"Current members: {dest_info['current']}\n"
            f"Remaining slots: {remaining_slots}\n"
            f"Total source members: {total_members}\n"
            f"Delay: 5-15 seconds between adds"
        )
        msg = await client.send_message("me", start_msg)
        
        success = 0
        failed = 0
        skipped = 0
        
        for member in members:
            if not active_stealing_tasks.get(account_num, True):
                break
                
            if success >= remaining_slots:
                break
                
            try:
                if getattr(member, 'deleted', False) or getattr(member, 'restricted', False):
                    skipped += 1
                    continue
                    
                await client(functions.channels.InviteToChannelRequest(
                    channel=dest_entity,
                    users=[member]
                ))
                success += 1
                
                delay = random.randint(5, 15)
                await asyncio.sleep(delay)
                
                if (success + failed + skipped) % 10 == 0:
                    progress_msg = (
                        f"Transferring members...\n\n"
                        f"Success: {success}\n"
                        f"Failed: {failed}\n"
                        f"Skipped: {skipped}\n"
                        f"Total: {success + failed + skipped}/{min(total_members, remaining_slots)}\n"
                        f"Current delay: {delay} seconds"
                    )
                    await msg.edit(progress_msg)
                    
            except Exception as e:
                failed += 1
                print(f"Failed to add member {getattr(member, 'id', 'Unknown')}: {str(e)}")
                await asyncio.sleep(20)
                
        result_msg = (
            f"Member transfer completed\n\n"
            f"Source: {getattr(source_entity, 'title', 'Unknown')}\n"
            f"Target: {getattr(dest_entity, 'title', 'Unknown')}\n\n"
            f"Success: {success}\n"
            f"Failed: {failed}\n"
            f"Skipped: {skipped}\n"
            f"Total: {success + failed + skipped}/{total_members}\n\n"
            f"New members in channel: {dest_info['current'] + success}/{dest_info['limit']}"
        )
        await msg.edit(result_msg)
        
    except Exception as e:
        print(f"Error in member transfer: {str(e)}")
        await client.send_message("me", f"Error: {str(e)}")
        
    finally:
        active_stealing_tasks[account_num] = False
        member_stealing[str(account_num)] = False
        save_settings()

async def discover_star_channels(client, account_num):
    """Discover new star channels using keywords"""
    try:
        dialogs = await client.get_dialogs(limit=200)
        
        for dialog in dialogs:
            if not hasattr(dialog.entity, 'title'):
                continue
                
            if any(keyword.lower() in getattr(dialog, 'name', '').lower() for keyword in STAR_KEYWORDS):
                if hasattr(dialog.entity, 'username') and dialog.entity.username:
                    if dialog.entity.username not in star_collection['channels']:
                        star_collection['channels'].add(dialog.entity.username)
                        save_star_channel(dialog.entity.username)
                        await client.send_message(
                            "me",
                            f"🌟 تم اكتشاف قناة نجوم جديدة:\n\n"
                            f"📢 القناة: @{dialog.entity.username}\n"
                            f"🏷️ الاسم: {getattr(dialog, 'name', 'Unknown')}\n\n"
                            f"#جمع_النجوم #اكتشاف"
                        )
        
        # Also search in Telegram
        for keyword in STAR_KEYWORDS:
            try:
                result = await client(functions.contacts.SearchRequest(
                    q=keyword,
                    limit=100
                ))
                
                for chat in result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        if chat.username not in star_collection['channels']:
                            star_collection['channels'].add(chat.username)
                            save_star_channel(chat.username)
                            await client.send_message(
                                "me",
                                f"🌟 تم اكتشاف قناة نجوم جديدة:\n\n"
                                f"📢 القناة: @{chat.username}\n"
                                f"🏷️ الاسم: {getattr(chat, 'title', 'Unknown')}\n\n"
                                f"#جمع_النجوم #اكتشاف"
                            )
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error searching for star channels: {str(e)}")
                await asyncio.sleep(30)
                
    except Exception as e:
        logger.error(f"Error in star channel discovery: {str(e)}")

def save_star_channel(username):
    """Save a star channel to the database"""
    conn = sqlite3.connect(STAR_DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO star_channels (username, last_checked, success_rate) VALUES (?, ?, ?)",
              (username, datetime.now().isoformat(), 0.5))
    conn.commit()
    conn.close()

async def collect_stars_from_channel(client, account_num, channel):
    """Collect stars from a specific channel"""
    try:
        entity = await client.get_entity(channel)
        
        # Try different commands to collect stars
        commands = ['/start', '/get', '/free', '/claim', 'ابدأ', 'جمع', 'هدية', 'النجوم', 'بريميوم']
        
        for cmd in commands:
            try:
                await client.send_message(entity, cmd)
                logger.info(f"Sent command {cmd} to {channel}")
                
                # Wait for bot response
                await asyncio.sleep(5)
                
                # Try to interact with bot messages
                async for message in client.iter_messages(entity, limit=3):
                    if message.is_reply:
                        try:
                            await message.click(0)  # Click first button if available
                            logger.info(f"Clicked button in {channel}")
                            break
                        except:
                            continue
                
                # Record success
                record_star_success(channel)
                star_collection['stats']['collected'][str(account_num)] = star_collection['stats']['collected'].get(str(account_num), 0) + 1
                save_settings()
                
                return True
                
            except FloodWaitError as e:
                logger.warning(f"Flood wait for {e.seconds} seconds from {channel}")
                await asyncio.sleep(e.seconds)
                continue
            except ChatWriteForbiddenError:
                logger.warning(f"Cannot write to channel {channel}")
                record_star_failure(channel)
                return False
            except Exception as e:
                logger.warning(f"Error with command {cmd} for {channel}: {str(e)}")
                continue
        
        return True
        
    except Exception as e:
        logger.error(f"Error collecting stars from {channel}: {str(e)}")
        record_star_failure(channel)
        return False

def record_star_success(channel):
    """Record successful star collection from channel"""
    conn = sqlite3.connect(STAR_DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE star_channels SET last_checked=?, success_rate=success_rate+0.1 WHERE username=?",
              (datetime.now().isoformat(), channel))
    conn.commit()
    conn.close()

def record_star_failure(channel):
    """Record failed star collection attempt"""
    conn = sqlite3.connect(STAR_DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE star_channels SET last_checked=?, success_rate=success_rate-0.1 WHERE username=?",
              (datetime.now().isoformat(), channel))
    conn.commit()
    conn.close()

async def run_star_collection(client, account_num):
    """Main star collection routine"""
    try:
        while star_collection['active_accounts'].get(str(account_num), False):
            # Discover new channels periodically
            if random.random() < 0.1:  # 10% chance to discover new channels
                await discover_star_channels(client, account_num)
            
            # Collect from existing channels
            if star_collection['channels']:
                channel = random.choice(list(star_collection['channels']))
                await collect_stars_from_channel(client, account_num, channel)
                
                # Update stats
                star_collection['stats']['channels_checked'][str(account_num)] = star_collection['stats']['channels_checked'].get(str(account_num), 0) + 1
                star_collection['stats']['last_check'][str(account_num)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_settings()
            
            # Random delay between operations
            delay = star_collection['delay'] * (0.8 + random.random() * 0.4)  # ±20% variation
            await asyncio.sleep(delay)
            
    except Exception as e:
        logger.error(f"Error in star collection for account {account_num}: {str(e)}")
        star_collection['active_accounts'][str(account_num)] = False
        save_settings()

async def start_star_collection(client, account_num):
    """Start star collection for an account"""
    try:
        if star_collection['active_accounts'].get(str(account_num), False):
            await client.send_message("me", f"✅ جمع النجوم مفعل بالفعل للحساب {account_num}")
            return

        star_collection['active_accounts'][str(account_num)] = True
        star_collection['stats']['collected'][str(account_num)] = star_collection['stats']['collected'].get(str(account_num), 0)
        star_collection['stats']['channels_checked'][str(account_num)] = star_collection['stats']['channels_checked'].get(str(account_num), 0)
        star_collection['stats']['last_check'][str(account_num)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        save_settings()
        
        await client.send_message("me", f"✅ تم تفعيل جمع النجوم للحساب {account_num}\n\n"
                              f"⏱ التأخير بين العمليات: {star_collection['delay']} ثانية\n"
                              f"📊 القنوات المعروفة: {len(star_collection['channels'])}\n\n"
                              f"سيبدأ الجمع تلقائياً في الخلفية")
        
        # Start collection in background
        asyncio.create_task(run_star_collection(client, account_num))
        
    except Exception as e:
        logger.error(f"Error starting star collection: {str(e)}")
        await client.send_message("me", f"❌ خطأ في تفعيل جمع النجوم: {str(e)}")

async def stop_star_collection(client, account_num):
    """Stop star collection for an account"""
    try:
        if not star_collection['active_accounts'].get(str(account_num), False):
            await client.send_message("me", f"⚠️ جمع النجوم غير مفعل للحساب {account_num}")
            return

        star_collection['active_accounts'][str(account_num)] = False
        save_settings()
        
        stats = star_collection['stats']
        await client.send_message("me", f"⏹ تم إيقاف جمع النجوم للحساب {account_num}\n\n"
                                   f"📊 الإحصائيات:\n"
                                   f"🌟 النجوم المجموعة: {stats['collected'].get(str(account_num), 0)}\n"
                                   f"📢 القنوات المفحوصة: {stats['channels_checked'].get(str(account_num), 0)}\n"
                                   f"⏱ آخر فحص: {stats['last_check'].get(str(account_num), 'غير متاح')}")
        
    except Exception as e:
        logger.error(f"Error stopping star collection: {str(e)}")
        await client.send_message("me", f"❌ خطأ في إيقاف جمع النجوم: {str(e)}")

def setup_handlers(client, account_num):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^s (\d+) (\d+)$'))
    async def swing(event):
        try:
            if event.is_reply:
                geteventText = event.text.split(" ")
                sleps = int(geteventText[1])
                range_num = int(geteventText[2])
                chatId = event.chat_id
                message = await event.get_reply_message()
                
                auto_posting_tasks[account_num] = True
                
                for i in range(range_num):
                    if not auto_posting_tasks.get(account_num, True):
                        break
                    await asyncio.sleep(sleps)
                    await client.send_message(chatId, message)
                
                if auto_posting_tasks.get(account_num, True):
                    await client.send_message("me", f"Auto-post completed in: {chatId} - Account {account_num}")
                else:
                    await client.send_message("me", f"Auto-post stopped manually in: {chatId} - Account {account_num}")
                
                auto_posting_tasks[account_num] = False
            else:
                await event.edit("Reply to a message to repeat it")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")
            auto_posting_tasks[account_num] = False
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ن0$'))
    async def stop_auto_posting(event):
        try:
            if auto_posting_tasks.get(account_num, False):
                auto_posting_tasks[account_num] = False
                await event.edit("✅ تم إيقاف النشر التلقائي")
            else:
                await event.edit("⚠️ لا يوجد نشر تلقائي نشط لإيقافه")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ح([01])$'))
    async def toggle_reply_tracking(event):
        try:
            state = int(event.pattern_match.group(1))
            reply_tracking[str(account_num)] = bool(state)
            save_settings()
            status = "✅ تم تفعيل" if state else "❌ تم تعطيل"
            await event.edit(f"{status} تتبع الردود للحساب {account_num}")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")
    
    @client.on(events.NewMessage(incoming=True))
    async def track_replies(event):
        try:
            if not reply_tracking.get(str(account_num), False):
                return
            
            if event.is_reply and event.sender_id != user_ids.get(account_num):
                replied_msg = await event.get_reply_message()
                
                if replied_msg and replied_msg.sender_id == user_ids.get(account_num):
                    chat = await event.get_chat()
                    chat_title = getattr(chat, 'title', "Private chat")
                    
                    sender = await event.get_sender()
                    sender_name = []
                    
                    if hasattr(sender, 'first_name') and sender.first_name:
                        sender_name.append(sender.first_name)
                    if hasattr(sender, 'last_name') and sender.last_name:
                        sender_name.append(sender.last_name)
                    
                    if not sender_name and hasattr(sender, 'username') and sender.username:
                        sender_name.append(f"@{sender.username}")
                    
                    if not sender_name:
                        sender_name.append(f"user_{sender.id}")
                    
                    sender_name = " ".join(sender_name).strip()
                    
                    message_text = event.text or "Non-text message (media)"
                    
                    chat_id = event.chat_id
                    if str(chat_id).startswith('-100'):
                        chat_id = int(str(chat_id)[4:])
                    
                    # إنشاء رابط الحساب الشخصي
                    user_link = f"https://t.me/{sender.username}" if hasattr(sender, 'username') and sender.username else f"tg://user?id={sender.id}"
                    
                    message = (
                        f"📨 رد جديد على رسالتك\n\n"
                        f"👤 المرسل: {sender_name}\n"
                        f"🔗 حساب المرسل: {user_link}\n"
                        f"📝 المحتوى: {message_text}\n"
                        f"💬 المجموعة: {chat_title}\n"
                        f"🔗 رابط الرسالة: https://t.me/c/{chat_id}/{event.id}"
                    )
                    
                    await client.send_message("me", message)
        except Exception as e:
            print(f"Error tracking replies for account {account_num}: {str(e)}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.س1 (.+?) (.+?)$'))
    async def start_stealing_members(event):
        try:
            source = event.pattern_match.group(1).strip()
            destination = event.pattern_match.group(2).strip()
            
            await event.edit(f"⏳ بدء نقل الأعضاء من {source} إلى {destination}...")
            await steal_members(client, account_num, source, destination)
            
        except Exception as e:
            await event.edit(f"Error: {str(e)}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.س0$'))
    async def stop_stealing_members(event):
        try:
            if active_stealing_tasks.get(account_num, False):
                active_stealing_tasks[account_num] = False
                member_stealing[str(account_num)] = False
                save_settings()
                await event.edit("⏹ تم إيقاف نقل الأعضاء")
            else:
                await event.edit("⚠️ لا يوجد عملية نقل أعضاء نشطة لهذا الحساب")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

    # Auto-Reply Handlers
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ر1$'))
    async def enable_auto_reply(event):
        try:
            auto_reply_settings['enabled'][str(account_num)] = True
            save_settings()
            await event.edit(f"✅ تم تفعيل الرد التلقائي للحساب {account_num}")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ر0$'))
    async def disable_auto_reply(event):
        try:
            auto_reply_settings['enabled'][str(account_num)] = False
            save_settings()
            await event.edit(f"❌ تم تعطيل الرد التلقائي للحساب {account_num}")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ر2 (.+)$'))
    async def set_auto_reply_message(event):
        try:
            message = event.pattern_match.group(1).strip()
            auto_reply_settings['message'][str(account_num)] = message
            save_settings()
            await event.edit(f"📝 تم تعيين رسالة الرد التلقائي للحساب {account_num}:\n\n{message}")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

    # Media Saving Handlers
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.و1$'))
    async def enable_media_saving(event):
        try:
            media_saving_settings[str(account_num)] = True
            save_settings()
            await event.edit(f"✅ تم تفعيل حفظ الوسائط الوقتية للحساب {account_num}")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.و0$'))
    async def disable_media_saving(event):
        try:
            media_saving_settings[str(account_num)] = False
            save_settings()
            await event.edit(f"❌ تم تعطيل حفظ الوسائط الوقتية للحساب {account_num}")
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

    # Star Collection Handlers
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نج1$'))
    async def enable_star_collection(event):
        """Enable star collection"""
        try:
            await start_star_collection(client, account_num)
            await event.edit(f"✅ تم تفعيل جمع النجوم للحساب {account_num}")
        except Exception as e:
            await event.edit(f"❌ خطأ: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نج0$'))
    async def disable_star_collection(event):
        """Disable star collection"""
        try:
            await stop_star_collection(client, account_num)
            await event.edit(f"⏹ تم إيقاف جمع النجوم للحساب {account_num}")
        except Exception as e:
            await event.edit(f"❌ خطأ: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نج2 (\d+)$'))
    async def set_star_delay(event):
        """Set delay between star collection operations"""
        try:
            delay = int(event.pattern_match.group(1))
            if delay < 10:
                await event.edit("⚠️ الحد الأدنى للتأخير هو 10 ثواني")
                return
                
            star_collection['delay'] = delay
            save_settings()
            await event.edit(f"✅ تم تعيين التأخير بين عمليات الجمع إلى {delay} ثانية")
        except Exception as e:
            await event.edit(f"❌ خطأ: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نج3$'))
    async def show_star_stats(event):
        """Show star collection stats"""
        try:
            stats = star_collection['stats']
            await event.edit(
                f"📊 إحصائيات جمع النجوم للحساب {account_num}:\n\n"
                f"🌟 النجوم المجموعة: {stats['collected'].get(str(account_num), 0)}\n"
                f"📢 القنوات المفحوصة: {stats['channels_checked'].get(str(account_num), 0)}\n"
                f"⏱ آخر فحص: {stats['last_check'].get(str(account_num), 'غير متاح')}\n\n"
                f"⏳ التأخير الحالي: {star_collection['delay']} ثانية\n"
                f"الحالة: {'✅ مفعل' if star_collection['active_accounts'].get(str(account_num), False) else '❌ معطل'}"
            )
        except Exception as e:
            await event.edit(f"❌ خطأ: {str(e)}")

    # New Auto-Post to Specific Channel Feature
    @client.on(events.NewMessage(outgoing=True, pattern=r'^sg (\d+) (\d+) (.+)$'))
    async def auto_post_to_channel(event):
        """نشر تلقائي في قناة محددة بالرد على الرسالة"""
        try:
            if event.is_reply:
                # تحليل الأوامر
                parts = event.text.split()
                delay_seconds = int(parts[1])
                repeat_count = int(parts[2])
                channel_link = parts[3]
                
                # الحصول على الرسالة المردود عليها
                replied_msg = await event.get_reply_message()
                
                # الحصول على كيان القناة
                try:
                    channel_entity = await client.get_entity(channel_link)
                except Exception as e:
                    await event.edit(f"❌ خطأ في العثور على القناة: {str(e)}")
                    return
                
                # تأكيد البدء
                await event.edit(f"⏳ بدء النشر التلقائي في القناة {getattr(channel_entity, 'title', channel_link)}\n"
                                f"⏱ التأخير: {delay_seconds} ثانية\n"
                                f"🔄 عدد المرات: {repeat_count}")
                
                # بدء النشر التلقائي
                auto_posting_tasks[account_num] = True
                
                success_count = 0
                for i in range(repeat_count):
                    if not auto_posting_tasks.get(account_num, False):
                        break
                    
                    try:
                        await client.send_message(
                            entity=channel_entity,
                            message=replied_msg
                        )
                        success_count += 1
                        
                        # عرض التقدم كل 5 مرات
                        if (i+1) % 5 == 0:
                            await event.edit(f"📤 جاري النشر...\n"
                                            f"✅ تم بنجاح: {success_count}/{repeat_count}\n"
                                            f"⏱ التالي بعد: {delay_seconds} ثانية")
                        
                        # انتظار بين كل نشر
                        if i < repeat_count - 1:
                            await asyncio.sleep(delay_seconds)
                            
                    except Exception as e:
                        print(f"Error in auto-post: {str(e)}")
                        await asyncio.sleep(30)  # انتظار أطول في حالة الخطأ
                
                # إرسال نتيجة النشر
                result_msg = (f"✅ تم الانتهاء من النشر التلقائي\n"
                            f"📌 القناة: {getattr(channel_entity, 'title', channel_link)}\n"
                            f"✅ النجاح: {success_count}\n"
                            f"❌ الفشل: {repeat_count - success_count}")
                
                await event.edit(result_msg)
                auto_posting_tasks[account_num] = False
                
            else:
                await event.edit("⚠️ يجب الرد على الرسالة المراد نشرها")
                
        except Exception as e:
            await event.edit(f"❌ خطأ: {str(e)}")
            auto_posting_tasks[account_num] = False

    @client.on(events.NewMessage(incoming=True))
    async def handle_auto_reply(event):
        try:
            account_str = str(account_num)
            
            if not auto_reply_settings['enabled'].get(account_str, False):
                return
            
            if not event.is_private:
                return
            
            sender = await event.get_sender()
            
            if sender.bot or sender.id == OWNER_ID:
                return
            
            if account_str not in auto_reply_settings['replied_users']:
                auto_reply_settings['replied_users'][account_str] = set()
            
            if sender.id not in auto_reply_settings['replied_users'][account_str]:
                reply_message = auto_reply_settings['message'].get(account_str, "شكراً على رسالتك!")
                await event.reply(reply_message)
                auto_reply_settings['replied_users'][account_str].add(sender.id)
                save_settings()
                
        except Exception as e:
            print(f"Error in auto-reply handler for account {account_num}: {str(e)}")

    @client.on(events.NewMessage(incoming=True))
    async def save_temporary_media(event):
        try:
            account_str = str(account_num)
            
            if not media_saving_settings.get(account_str, False):
                return
            
            # تحقق من أن الرسالة من محادثة خاصة وليست من مجموعة أو قناة
            if not event.is_private:
                return
            
            # تحقق من أن الرسالة تحتوي على وسائط وقتية فقط
            if event.media and hasattr(event.media, 'ttl_seconds'):
                media_path = await event.download_media()
                
                sender = await event.get_sender()
                sender_name = []
                
                first_name = getattr(sender, 'first_name', '')
                if first_name:
                    sender_name.append(first_name)
                
                last_name = getattr(sender, 'last_name', '')
                if last_name:
                    sender_name.append(last_name)
                
                if not sender_name:
                    username = getattr(sender, 'username', '')
                    if username:
                        sender_name.append(f"@{username}")
                    else:
                        sender_name.append(f"user_{sender.id}")
                
                sender_name = " ".join(sender_name).strip()
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                caption = (
                    f"🖼️ وسائط وقتية\n\n"
                    f"👤 المرسل: {sender_name}\n"
                    f"⏰ التاريخ: {now}\n"
                    f"🔗 المصدر: https://t.me/c/{event.chat_id}/{event.id}"
                )
                
                await client.send_file(
                    'me',
                    media_path,
                    caption=caption,
                    force_document=True
                )
                
                if os.path.exists(media_path):
                    os.remove(media_path)
                
        except Exception as e:
            print(f"Error saving temporary media for account {account_num}: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.الاوامر$'))
    async def show_commands(event):
        try:
            commands = [
                "📜 قائمة الأوامر المتاحة:",
                "",
                "🔹 النشر التلقائي:",
                "- s [ثواني] [عدد] - نشر رسالة معينة تلقائياً (الرد على الرسالة)",
                "- sg [ثواني] [عدد] [رابط المجموعة] - نشر في مجموعة محددة (الرد على الرسالة)",
                "- .ن0 - إيقاف النشر التلقائي",
                "",
                "🔹 تتبع الردود:",
                "- .ح1 - تفعيل تتبع الردود",
                "- .ح0 - تعطيل تتبع الردود",
                "",
                "🔹 نقل الأعضاء:",
                "- .س1 [المصدر] [الهدف] - بدء نقل الأعضاء",
                "- .س0 - إيقاف نقل الأعضاء",
                "",
                "🔹 الرد التلقائي:",
                "- .ر1 - تفعيل الرد التلقائي",
                "- .ر0 - تعطيل الرد التلقائي",
                "- .ر2 [رسالة] - تعيين رسالة الرد التلقائي",
                "",
                "🔹 حفظ الوسائط الوقتية:",
                "- .و1 - تفعيل حفظ الوسائط الوقتية",
                "- .و0 - تعطيل حفظ الوسائط الوقتية",
                "",
                "🔹 جمع النجوم:",
                "- .نج1 - تفعيل جمع النجوم التلقائي",
                "- .نج0 - إيقاف جمع النجوم",
                "- .نج2 [ثواني] - تعيين التأخير بين العمليات",
                "- .نج3 - عرض إحصائيات الجمع",
                "",
                "🔹 أخرى:",
                "- .الاوامر - عرض هذه القائمة"
            ]
            
            await event.edit("\n".join(commands))
        except Exception as e:
            await event.edit(f"Error: {str(e)}")

async def main():
    print("Starting advanced Telegram bot...")
    
    load_settings()
    init_star_db()
    
    await start_all_clients()
    await get_user_ids()
    
    for i, client in enumerate(clients, 1):
        setup_handlers(client, i)
        active_stealing_tasks[i] = False
        auto_posting_tasks[i] = False
        if str(i) not in auto_reply_settings['replied_users']:
            auto_reply_settings['replied_users'][str(i)] = set()
        if str(i) not in media_saving_settings:
            media_saving_settings[str(i)] = False
        if str(i) not in star_collection['active_accounts']:
            star_collection['active_accounts'][str(i)] = False
    
    print("All systems operational!")
    print("Available commands:")
    print("- s [seconds] [count] - Auto-post message (reply to message)")
    print("- sg [seconds] [count] [channel link] - Auto-post to specific channel (reply to message)")
    print("- .ن0 - Stop auto-posting")
    print("- .ح1 - Enable reply tracking")
    print("- .ح0 - Disable reply tracking")
    print("- .س1 [source] [destination] - Start member transfer")
    print("- .س0 - Stop member transfer")
    print("- .ر1 - Enable auto reply")
    print("- .ر0 - Disable auto reply")
    print("- .ر2 [message] - Set auto reply message")
    print("- .و1 - Enable temporary media saving")
    print("- .و0 - Disable temporary media saving")
    print("- .نج1 - Enable star collection")
    print("- .نج0 - Disable star collection")
    print("- .نج2 [seconds] - Set collection delay")
    print("- .نج3 - Show star collection stats")
    print("- .الاوامر - Show all commands")
    
    await asyncio.gather(*[client.run_until_disconnected() for client in clients])

if __name__ == "__main__":
    asyncio.run(main())
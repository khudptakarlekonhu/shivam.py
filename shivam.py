import sqlite3
import telebot
import time
import os
from threading import Thread
from flask import Flask
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==================== RENDER 24/7 KEEP ALIVE SERVER ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot is Running 24/7 on Render!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8721485106:AAGaIJfOkrxEQlOmJWd7MxfYDy3wCw07v9I"
OWNER_ID = 5647156798
OWNER_USERNAME = "@sidxzz"

CHANNELS = [
    {"username": "@ordermonitorbysid", "link": "https://t.me/ordermonitorbysid", "name": "Monitoring Channel"},
    {"username": "@completed_ordersbysid", "link": "https://t.me/completed_ordersbysid", "name": "Completed Orders Channel"},
    {"username": "@DRK_GARENA_INFO", "link": "https://t.me/DRK_GARENA_INFO", "name": "DRK Garena Info"}
]

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

DEFAULT_PRICES = {
    "Instagram Likes": 5,
    "Instagram Views": 2,
    "Instagram Followers": 20,
    "Facebook Likes": 5,
    "Facebook Views": 2,
    "Facebook Followers": 15,
    "YouTube Subscribers": 30,
    "YouTube Likes": 10,
    "Telegram Members": 15,
    "Telegram Channel Views": 1,
    "Telegram Reactions": 3,
    "WhatsApp Channel Members": 25,
    "WhatsApp International Number": 150
}

MIN_ORDER_LIMITS = {
    "Instagram Likes": 100,
    "Instagram Views": 100,
    "Facebook Likes": 100,
    "Facebook Views": 100,
    "YouTube Likes": 100,
    "Telegram Channel Views": 100,
    "Telegram Reactions": 100,
    "Instagram Followers": 50,
    "Facebook Followers": 50,
    "YouTube Subscribers": 50,
    "Telegram Members": 50,
    "WhatsApp Channel Members": 50,
    "WhatsApp International Number": 1
}

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS redeem_codes (
            code TEXT PRIMARY KEY,
            coins INTEGER,
            max_uses INTEGER,
            used_count INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_redeemed (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    ''')
    
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_reward', 10)")
    for srv, price in DEFAULT_PRICES.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (f"price_{srv}", price))

    conn.commit()
    conn.close()

def get_setting(key, default=0):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else default

def set_setting(key, value):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, coins, referred_by) VALUES (?, ?, ?, ?)",
                   (user_id, username, 0, referred_by))
    
    ref_reward = get_setting('referral_reward', 10)
    if referred_by and referred_by != user_id:
        cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (ref_reward, referred_by))
        try:
            bot.send_message(referred_by, f"🎉 Aapke link se kisi ne join kiya! Aapko +{ref_reward} Coins mile!")
        except Exception:
            pass
    conn.commit()
    conn.close()

def update_coins(user_id, amount):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    def set_exact_coins(user_id, amount):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_total_users_count():
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_top_referrals(limit=10):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT referred_by, COUNT(*) as ref_count 
        FROM users 
        WHERE referred_by IS NOT NULL 
        GROUP BY referred_by 
        ORDER BY ref_count DESC 
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_user_referral_count(user_id):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_user_ids():
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# ==================== REDEEM CODE FUNCTIONS ====================
def create_redeem_code(code, coins, max_uses):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO redeem_codes (code, coins, max_uses, used_count) VALUES (?, ?, ?, 0)", (code, coins, max_uses))
    conn.commit()
    conn.close()

def use_redeem_code(user_id, code):
    conn = sqlite3.connect('social_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT coins, max_uses, used_count FROM redeem_codes WHERE code = ?", (code,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return False, "❌ Ye Redeem Code invalid hai!"
    
    coins, max_uses, used_count = res
    if used_count >= max_uses:
        conn.close()
        return False, "❌ Is Redeem Code ki limit khatam ho chuki hai!"
    
    cursor.execute("SELECT * FROM user_redeemed WHERE user_id = ? AND code = ?", (user_id, code))
    if cursor.fetchone():
        conn.close()
        return False, "⚠️ Aapne is code ko pehle hi redeem kar liya hai!"
    
    cursor.execute("INSERT INTO user_redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
    cursor.execute("UPDATE redeem_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (coins, user_id))
    
    conn.commit()
    conn.close()
    return True, f"🎉 Mubarak ho! Aapko <b>+{coins} Coins</b> mil gaye hain!"
# ==================== FORCE JOIN CHECKER ====================
def is_user_joined(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch["username"], user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                return False
        except Exception:
            pass
    return True

def force_join_markup():
    markup = InlineKeyboardMarkup()
    for ch in CHANNELS:
        markup.add(InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link']))
    markup.add(InlineKeyboardButton("✅ Verify / Joined All", callback_data="check_joined"))
    return markup

# ==================== KEYBOARDS / MENUS ====================
def main_menu(user_id):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(KeyboardButton("📸 Instagram"), KeyboardButton("📘 Facebook"))
    markup.add(KeyboardButton("▶️ YouTube"), KeyboardButton("💬 WhatsApp"))
    markup.add(KeyboardButton("✈️ Telegram"), KeyboardButton("👑 Owner Info"))
    markup.add(KeyboardButton("💰 My Balance"), KeyboardButton("🔗 Refer & Earn"))
    markup.add(KeyboardButton("🎁 Redeem Code"))
    
    if user_id == OWNER_ID:
        markup.add(KeyboardButton("⚙️ Owner Control Panel"))
        
    return markup

def get_service_price(service_name):
    return get_setting(f"price_{service_name}", DEFAULT_PRICES.get(service_name, 1))

def get_instagram_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"❤️ Likes ({get_service_price('Instagram Likes')} Coins)", callback_data="srv_Instagram Likes"))
    markup.add(InlineKeyboardButton(f"👁️ Views ({get_service_price('Instagram Views')} Coins)", callback_data="srv_Instagram Views"))
    markup.add(InlineKeyboardButton(f"👤 Followers ({get_service_price('Instagram Followers')} Coins)", callback_data="srv_Instagram Followers"))
    return markup

def get_facebook_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"👍 Likes ({get_service_price('Facebook Likes')} Coins)", callback_data="srv_Facebook Likes"))
    markup.add(InlineKeyboardButton(f"👁️ Views ({get_service_price('Facebook Views')} Coins)", callback_data="srv_Facebook Views"))
    markup.add(InlineKeyboardButton(f"👤 Followers ({get_service_price('Facebook Followers')} Coins)", callback_data="srv_Facebook Followers"))
    return markup

def get_youtube_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"🔴 Subscribers ({get_service_price('YouTube Subscribers')} Coins)", callback_data="srv_YouTube Subscribers"))
    markup.add(InlineKeyboardButton(f"👍 Likes ({get_service_price('YouTube Likes')} Coins)", callback_data="srv_YouTube Likes"))
    return markup

def get_telegram_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"👥 Members ({get_service_price('Telegram Members')} Coins)", callback_data="srv_Telegram Members"))
    markup.add(InlineKeyboardButton(f"👁️ Views ({get_service_price('Telegram Channel Views')} Coins)", callback_data="srv_Telegram Channel Views"))
    markup.add(InlineKeyboardButton(f"🔥 Reactions ({get_service_price('Telegram Reactions')} Coins)", callback_data="srv_Telegram Reactions"))
    return markup

def get_whatsapp_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"📢 Channel Members ({get_service_price('WhatsApp Channel Members')} Coins)", callback_data="srv_WhatsApp Channel Members"))
    markup.add(InlineKeyboardButton(f"🌐 Intl. Number ({get_service_price('WhatsApp International Number')} Coins)", callback_data="srv_WhatsApp International Number"))
    return markup

def owner_panel_keyboard():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(KeyboardButton("➕ Add Coins"), KeyboardButton("➖ Remove Coins"))
    markup.add(KeyboardButton("✏️ Set Exact Coins"), KeyboardButton("📊 Total Users"))
    markup.add(KeyboardButton("🏆 Top Referrals"), KeyboardButton("👥 User Ref Stats"))
    markup.add(KeyboardButton("🎁 Change Referral Reward"))
    markup.add(KeyboardButton("💲 Edit Service Prices"))
    markup.add(KeyboardButton("📢 Broadcast (Msg for All)"))
    markup.add(KeyboardButton("🎟️ Create Redeem Code"))
    return markup
    # ==================== HANDLERS ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    text_args = message.text.split()
    referred_by = int(text_args[1]) if len(text_args) > 1 and text_args[1].isdigit() else None

    if not is_user_joined(user_id):
        bot.send_message(
            message.chat.id,
            f"⚠️ <b>Access Denied!</b>\n\nBot ko use karne ke liye aapko hamare sabhi teeno official channels ko join karna hoga:\n\n1. {CHANNELS[0]['link']}\n2. {CHANNELS[1]['link']}\n3. {CHANNELS[2]['link']}\n\nJoin karne ke baad <b>Verify / Joined All</b> button dabayein:",
            reply_markup=force_join_markup(),
            parse_mode="HTML"
        )
        return

    if not get_user(user_id):
        add_user(user_id, username, referred_by)
        bot.send_message(message.chat.id, f"👋 Welcome {username}! Bot me aapka swagat hai.", reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, f"Welcome back, {username}!", reply_markup=main_menu(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "check_joined")
def check_join_callback(call):
    user_id = call.from_user.id
    if is_user_joined(user_id):
        bot.answer_callback_query(call.id, "✅ Verification Successful!")
        username = call.from_user.username or call.from_user.first_name
        if not get_user(user_id):
            add_user(user_id, username)
        bot.send_message(call.message.chat.id, "🎉 Verification Complete! Aap bot use kar sakte hain.", reply_markup=main_menu(user_id))
    else:
        bot.answer_callback_query(call.id, "❌ Aapne abhi tak saare channels join nahi kiye!", show_alert=True)

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id

    if not is_user_joined(user_id):
        bot.send_message(
            message.chat.id,
            f"⚠️ <b>Access Denied!</b>\n\nKripya pehle teeno channels join karein:",
            reply_markup=force_join_markup(),
            parse_mode="HTML"
        )
        return

    user = get_user(user_id)
    if not user:
        add_user(user_id, message.from_user.username or message.from_user.first_name)
        user = get_user(user_id)

    text = message.text

    if text == "📸 Instagram":
        bot.send_message(message.chat.id, "👇 <b>Instagram Services</b> me se choose karein:", reply_markup=get_instagram_menu(), parse_mode="HTML")

    elif text == "📘 Facebook":
        bot.send_message(message.chat.id, "👇 <b>Facebook Services</b> me se choose karein:", reply_markup=get_facebook_menu(), parse_mode="HTML")

    elif text == "▶️ YouTube":
        bot.send_message(message.chat.id, "👇 <b>YouTube Services</b> me se choose karein:", reply_markup=get_youtube_menu(), parse_mode="HTML")

    elif text == "💬 WhatsApp":
        bot.send_message(message.chat.id, "👇 <b>WhatsApp Services</b> me se choose karein:", reply_markup=get_whatsapp_menu(), parse_mode="HTML")

    elif text == "✈️ Telegram":
        bot.send_message(message.chat.id, "👇 <b>Telegram Services</b> me se choose karein:", reply_markup=get_telegram_menu(), parse_mode="HTML")

    elif text == "👑 Owner Info":
        msg = (
            f"👑 <b>Owner / Admin Details</b>\n\nSupport & Inquiries:\n"
            f"👉 <b>Username:</b> {OWNER_USERNAME}\n"
            f"👉 <b>Owner ID:</b> <code>{OWNER_ID}</code>\n"
            f"👉 <b>Monitoring:</b> {CHANNELS[0]['link']}\n"
            f"👉 <b>Completed Orders:</b> {CHANNELS[1]['link']}\n"
            f"👉 <b>Garena Info:</b> {CHANNELS[2]['link']}"
        )
        bot.send_message(message.chat.id, msg, parse_mode="HTML")

    elif text == "💰 My Balance":
        my_refs = get_user_referral_count(user_id)
        bot.send_message(message.chat.id, f"💳 <b>Aapka Balance:</b> <code>{user[2]}</code> Coins\n👥 <b>Total Referrals:</b> <code>{my_refs}</code> Users", parse_mode="HTML")

    elif text == "🔗 Refer & Earn":
        bot_info = bot.get_me()
        ref_reward = get_setting('referral_reward', 10)
        my_refs = get_user_referral_count(user_id)
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        msg = f"🎁 <b>Refer & Earn Coins</b>\n\nApne friends ko invite karein aur har referral par <b>{ref_reward} Coins</b> paayein!\n\n👥 Aapke Total Referrals: <code>{my_refs}</code> Users\n\nAapka Referral Link:\n<code>{ref_link}</code>"
        bot.send_message(message.chat.id, msg, parse_mode="HTML")

    elif text == "🎁 Redeem Code":
        user_states[user_id] = {'step': 'WAITING_REDEEM_CODE'}
        bot.send_message(message.chat.id, "🎟️ Apna <b>Redeem Code</b> enter karein:", parse_mode="HTML")

    elif text == "⚙️ Owner Control Panel":
        if user_id == OWNER_ID:
            send_admin_panel(message.chat.id)
        else:
            bot.send_message(message.chat.id, "❌ Access Denied!")
            def send_admin_panel(chat_id):
    msg = "⚙️ <b>Owner Control Panel</b>\n\nNeeche diye gaye buttons se options choose karein:"
    bot.send_message(chat_id, msg, reply_markup=owner_panel_keyboard(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv_"))
def service_callback(call):
    user_id = call.from_user.id
    service_name = call.data.replace("srv_", "")
    price = get_service_price(service_name)
    min_limit = MIN_ORDER_LIMITS.get(service_name, 50)
    
    user_states[user_id] = {'step': 'WAITING_ORDER_LINK', 'service': service_name, 'price': price, 'min_limit': min_limit}
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"📦 Aapne select kiya: <b>{service_name}</b>\n💰 Price: <b>{price} Coins</b>\n📉 Min Limit: <b>{min_limit}</b>\n\nKripya apne order ka <b>Link</b> aur <b>Quantity</b> bhejein:",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def handle_states(message):
    user_id = message.from_user.id
    state = user_states[user_id].get('step')
    text = message.text

    if state == 'WAITING_REDEEM_CODE':
        del user_states[user_id]
        success, resp = use_redeem_code(user_id, text.strip())
        bot.send_message(message.chat.id, resp, parse_mode="HTML")

    elif state == 'WAITING_ADD_COINS':
        del user_states[user_id]
        try:
            target_id, amount = map(int, text.split())
            update_coins(target_id, amount)
            bot.send_message(message.chat.id, f"✅ Success! User <code>{target_id}</code> me +{amount} coins add kar diye gaye hain.", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Galat format! Use karein: <code>USER_ID COINS</code>", parse_mode="HTML")

    elif state == 'WAITING_REMOVE_COINS':
        del user_states[user_id]
        try:
            target_id, amount = map(int, text.split())
            update_coins(target_id, -amount)
            bot.send_message(message.chat.id, f"✅ Success! User <code>{target_id}</code> se -{amount} coins kaat liye gaye hain.", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Galat format! Use karein: <code>USER_ID COINS</code>", parse_mode="HTML")

    elif state == 'WAITING_EXACT_COINS':
        del user_states[user_id]
        try:
            target_id, amount = map(int, text.split())
            set_exact_coins(target_id, amount)
            bot.send_message(message.chat.id, f"✅ Success! User <code>{target_id}</code> ke coins set karke {amount} kar diye gaye hain.", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Galat format! Use karein: <code>USER_ID COINS</code>", parse_mode="HTML")

    elif state == 'WAITING_USER_REF_STATS':
        del user_states[user_id]
        try:
            target_id = int(text.strip())
            refs = get_user_referral_count(target_id)
            bot.send_message(message.chat.id, f"👥 User <code>{target_id}</code> ke total referrals: <b>{refs}</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Invalid User ID!", parse_mode="HTML")

    elif state == 'WAITING_REF_REWARD':
        del user_states[user_id]
        try:
            new_reward = int(text.strip())
            set_setting('referral_reward', new_reward)
            bot.send_message(message.chat.id, f"✅ Referral reward update karke <b>{new_reward} Coins</b> kar diya gaya hai!", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Kripya valid number enter karein!", parse_mode="HTML")

    elif state == 'WAITING_EDIT_PRICE':
        try:
            parts = text.split(maxsplit=1)
            srv_name = parts[0]
            new_price = int(parts[1])
            set_setting(f"price_{srv_name}", new_price)
            del user_states[user_id]
            bot.send_message(message.chat.id, f"✅ <b>{srv_name}</b> ka naya price <b>{new_price} Coins</b> set ho gaya hai!", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Galat format! Use karein: <code>Service_Name Price</code>", parse_mode="HTML")

    elif state == 'WAITING_BROADCAST':
        del user_states[user_id]
        users = get_all_user_ids()
        success_count = 0
        bot.send_message(message.chat.id, "📢 Broadcast shuru ho gaya hai...")
        for uid in users:
            try:
                bot.send_message(uid, text, parse_mode="HTML")
                success_count += 1
                time.sleep(0.1)
            except Exception:
                pass
        bot.send_message(message.chat.id, f"✅ Broadcast poora ho gaya!\nSuccessfully sent to: <b>{success_count}</b> users.", parse_mode="HTML")

    elif state == 'WAITING_CREATE_REDEEM':
        try:
            parts = text.split()
            code = parts[0]
            coins = int(parts[1])
            max_uses = int(parts[2])
            create_redeem_code(code, coins, max_uses)
            del user_states[user_id]
            bot.send_message(message.chat.id, f"✅ Redeem Code successfully create ho gaya!\n\n🎟️ Code: <code>{code}</code>\n💰 Coins: <b>{coins}</b>\n👥 Max Uses: <b>{max_uses}</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "❌ Galat format! Use karein: <code>CODE COINS MAX_USES</code>", parse_mode="HTML")

    elif state == 'WAITING_ORDER_LINK':
        data = user_states[user_id]
        srv_name = data['service']
        price = data['price']
        del user_states[user_id]
        
        user = get_user(user_id)
        user_coins = user[2]
        
        if user_coins < price:
            bot.send_message(message.chat.id, f"❌ Aapke paas kaafi coins nahi hain!\nRequired: <b>{price}</b>, Aapke paas hain: <b>{user_coins}</b>", parse_mode="HTML")
            return
        
        update_coins(user_id, -price)
        remaining_coins = user_coins - price
        
        order_text = (
            f"🚨 <b>New Order Received!</b>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔗 <b>Service:</b> {srv_name}\n"
            f"🔗 <b>Details/Link:</b> {text}\n"
            f"💳 <b>Paid Price:</b> {price} Coins"
        )
        
        try:
            bot.send_message(CHANNELS[0]['username'], order_text, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending to monitoring channel: {e}")
            
        bot.send_message(message.chat.id, f"✅ Aapka order successfully place ho gaya hai!\n💳 Kat gaye Coins: <b>{price}</b>\n📉 Bacha hua Balance: <b>{remaining_coins} Coins</b>", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.from_user.id == OWNER_ID and message.text in [
    "➕ Add Coins", "➖ Remove Coins", "✏️ Set Exact Coins", "📊 Total Users", 
    "🏆 Top Referrals", "👥 User Ref Stats", "🎁 Change Referral Reward", 
    "💲 Edit Service Prices", "📢 Broadcast (Msg for All)", "🎟️ Create Redeem Code"
])
def handle_admin_commands(message):
    text = message.text
    user_id = message.from_user.id

    if text == "➕ Add Coins":
        user_states[user_id] = {'step': 'WAITING_ADD_COINS'}
        bot.send_message(message.chat.id, "➕ Format bhejein: <code>USER_ID COINS</code>", parse_mode="HTML")
    elif text == "➖ Remove Coins":
        user_states[user_id] = {'step': 'WAITING_REMOVE_COINS'}
        bot.send_message(message.chat.id, "➖ Format bhejein: <code>USER_ID COINS</code>", parse_mode="HTML")
    elif text == "✏️ Set Exact Coins":
        user_states[user_id] = {'step': 'WAITING_EXACT_COINS'}
        bot.send_message(message.chat.id, "✏️ Format bhejein: <code>USER_ID COINS</code>", parse_mode="HTML")
    elif text == "📊 Total Users":
        total = get_total_users_count()
        bot.send_message(message.chat.id, f"📊 Total registered users in bot: <b>{total}</b>", parse_mode="HTML")
    elif text == "🏆 Top Referrals":
        top = get_top_referrals(10)
        msg = "🏆 <b>Top Referrers:</b>\n\n"
        for idx, (uid, count) in enumerate(top, 1):
            msg += f"{idx}. User <code>{uid}</code> - <b>{count}</b> Refs\n"
        bot.send_message(message.chat.id, msg, parse_mode="HTML")
    elif text == "👥 User Ref Stats":
        user_states[user_id] = {'step': 'WAITING_USER_REF_STATS'}
        bot.send_message(message.chat.id, "👥 User ID bhejein:", parse_mode="HTML")
    elif text == "🎁 Change Referral Reward":
        user_states[user_id] = {'step': 'WAITING_REF_REWARD'}
        bot.send_message(message.chat.id, "🎁 Naya referral reward amount bhejein:", parse_mode="HTML")
    elif text == "💲 Edit Service Prices":
        user_states[user_id] = {'step': 'WAITING_EDIT_PRICE'}
        bot.send_message(message.chat.id, "💲 Format bhejein: <code>Service_Name New_Price</code>", parse_mode="HTML")
    elif text == "📢 Broadcast (Msg for All)":
        user_states[user_id] = {'step': 'WAITING_BROADCAST'}
        bot.send_message(message.chat.id, "📢 Broadcast message type karein:", parse_mode="HTML")
    elif text == "🎟️ Create Redeem Code":
        user_states[user_id] = {'step': 'WAITING_CREATE_REDEEM'}
        bot.send_message(message.chat.id, "🎟️ Format bhejein: <code>CODE COINS MAX_USES</code>", parse_mode="HTML")

# ==================== MAIN RUNNER ====================
if __name__ == '__main__':
    init_db()
    keep_alive()
    print("Bot is starting...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(3)
                

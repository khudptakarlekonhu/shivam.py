import os
import time
import logging
from threading import Thread
from flask import Flask
from pymongo import MongoClient
import telebot
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
BOT_TOKEN = os.getenv("BOT_TOKEN", "8721485106:AAF9XoGbDs1PNEPiTmHv6SFhX0z7qRcCu8M")
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
    "WhatsApp International Number": 150,
    "Play Store Redeem Code": 50
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
    "WhatsApp International Number": 1,
    "Play Store Redeem Code": 1
}

# ==================== MONGODB DATABASE SETUP ====================
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("❌ CRITICAL ERROR: MONGO_URI environment variable is missing!")

client = MongoClient(MONGO_URI)
db = client["shivam_bot_db"]

users_collection = db["users"]
settings_collection = db["settings"]
redeem_collection = db["redeem_codes"]
user_redeemed_collection = db["user_redeemed"]

def init_db():
    if settings_collection.find_one({"key": "referral_reward"}) is None:
        settings_collection.insert_one({"key": "referral_reward", "value": 10})
        
    for srv, price in DEFAULT_PRICES.items():
        if settings_collection.find_one({"key": f"price_{srv}"}) is None:
            settings_collection.insert_one({"key": f"price_{srv}", "value": price})
            
    print("✅ MongoDB Database Initialized Successfully!")

def get_setting(key, default=0):
    res = settings_collection.find_one({"key": key})
    return res["value"] if res else default

def set_setting(key, value):
    settings_collection.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

def get_user(user_id):
    return users_collection.find_one({"user_id": user_id})

def add_user(user_id, username, referred_by=None):
    existing_user = users_collection.find_one({"user_id": user_id})
    
    if not existing_user:
        users_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "coins": 0,
            "referred_by": referred_by
        })
        
        ref_reward = get_setting('referral_reward', 10)
        if referred_by and referred_by != user_id:
            users_collection.update_one({"user_id": referred_by}, {"$inc": {"coins": ref_reward}})
            try:
                bot.send_message(referred_by, f"🎉 Aapke link se kisi ne join kiya! Aapko +{ref_reward} Coins mile!")
            except Exception:
                pass
    elif existing_user.get("referred_by") is None and referred_by and referred_by != user_id:
        users_collection.update_one({"user_id": user_id}, {"$set": {"referred_by": referred_by}})
        ref_reward = get_setting('referral_reward', 10)
        users_collection.update_one({"user_id": referred_by}, {"$inc": {"coins": ref_reward}})
        try:
            bot.send_message(referred_by, f"🎉 Aapke link se kisi ne join kiya! Aapko +{ref_reward} Coins mile!")
        except Exception:
            pass

def update_coins(user_id, amount):
    users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": amount}})

def set_exact_coins(user_id, amount):
    users_collection.update_one({"user_id": user_id}, {"$set": {"coins": amount}}, upsert=True)

def get_total_users_count():
    return users_collection.count_documents({})
def get_top_referrals(limit=10):
    pipeline = [
        {"$match": {"referred_by": {"$ne": None}}},
        {"$group": {"_id": "$referred_by", "ref_count": {"$sum": 1}}},
        {"$sort": {"ref_count": -1}},
        {"$limit": limit}
    ]
    results = list(users_collection.aggregate(pipeline))
    return [(item["_id"], item["ref_count"]) for item in results]

def get_user_referral_count(user_id):
    return users_collection.count_documents({"referred_by": user_id})
    
def get_all_user_ids():
    users = users_collection.find({}, {"user_id": 1})
    return [doc["user_id"] for doc in users]

# ==================== REDEEM CODE FUNCTIONS ====================
def create_redeem_code(code, coins, max_uses):
    redeem_collection.update_one(
        {"code": code},
        {"$set": {"coins": coins, "max_uses": max_uses, "used_count": 0}},
        upsert=True
    )

def use_redeem_code(user_id, code):
    code_data = redeem_collection.find_one({"code": code})
    if not code_data:
        return False, "❌ Ye Redeem Code invalid hai!"
    
    if code_data["used_count"] >= code_data["max_uses"]:
        return False, "❌ Is Redeem Code ki limit khatam ho chuki hai!"
    
    already_used = user_redeemed_collection.find_one({"user_id": user_id, "code": code})
    if already_used:
        return False, "⚠️ Aapne is code ko pehle hi redeem kar liya hai!"
    
    user_redeemed_collection.insert_one({"user_id": user_id, "code": code})
    redeem_collection.update_one({"code": code}, {"$inc": {"used_count": 1}})
    users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": code_data["coins"]}})
    
    return True, f"🎉 Mubarak ho! Aapko <b>+{code_data['coins']} Coins</b> mil gaye hain!"

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
    markup.add(KeyboardButton("💳 Buy Play Store Redeem Code"))
    
    if user_id == OWNER_ID:
        markup.add(KeyboardButton("⚙️ Owner Control Panel"))
        
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
    markup.add(KeyboardButton("🔙 Back to Main Menu"))
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

    if user_id == OWNER_ID and text == "⚙️ Owner Control Panel":
        ref_reward = get_setting('referral_reward', 10)
        bot.send_message(message.chat.id, f"👑 <b>Welcome Owner!</b>\n💡 Current Referral Reward: <code>{ref_reward}</code> Coins\nNiche se options select karein:", reply_markup=owner_panel_keyboard(), parse_mode="HTML")
        return

    if user_id == OWNER_ID and text == "🔙 Back to Main Menu":
        bot.send_message(message.chat.id, "🏠 Main Menu me wapas aa gaye hain:", reply_markup=main_menu(user_id), parse_mode="HTML")
        if user_id in user_states:
            del user_states[user_id]
        return

    if user_id == OWNER_ID and text in [
        "➕ Add Coins", "➖ Remove Coins", "✏️ Set Exact Coins", "📊 Total Users",
        "🏆 Top Referrals", "👥 User Ref Stats", "🎁 Change Referral Reward",
        "💲 Edit Service Prices", "📢 Broadcast (Msg for All)", "🎟️ Create Redeem Code"
    ]:
        if text == "📊 Total Users":
            total_users = get_total_users_count()
            bot.send_message(message.chat.id, f"📊 <b>Bot Statistics:</b>\n\n👥 Total Users Joined: <code>{total_users}</code>", parse_mode="HTML")
        
        elif text == "🏆 Top Referrals":
            top_list = get_top_referrals(10)
            if not top_list:
                bot.send_message(message.chat.id, "ℹ️ Abhi tak kisi ne referral nahi kiya hai.")
            else:
                msg = "🏆 <b>Top 10 Referrers List:</b>\n\n"
                for idx, item in enumerate(top_list, 1):
                    u_info = get_user(item[0])
                    uname = u_info.get("username", "Unknown") if u_info else "Unknown"
                    msg += f"{idx}. ID: <code>{item[0]}</code> (@{uname}) ➔ <b>{item[1]}</b> Referrals\n"
                bot.send_message(message.chat.id, msg, parse_mode="HTML")

        elif text == "👥 User Ref Stats":
            user_states[user_id] = {'step': 'ADMIN_CHECK_USER_REF'}
            bot.send_message(message.chat.id, "🔍 Kripya target User ki <b>Telegram ID</b> enter karein:", parse_mode="HTML")

        elif text == "➕ Add Coins":
            user_states[user_id] = {'step': 'ADMIN_INPUT_COINS', 'action': 'add'}
            bot.send_message(message.chat.id, "✏️ Type: <code>User_ID Coins</code>\n(Example: <code>123456789 100</code>)", parse_mode="HTML")

        elif text == "➖ Remove Coins":
            user_states[user_id] = {'step': 'ADMIN_INPUT_COINS', 'action': 'remove'}
            bot.send_message(message.chat.id, "✏️ Type: <code>User_ID Coins</code>\n(Example: <code>123456789 100</code>)", parse_mode="HTML")

        elif text == "✏️ Set Exact Coins":
            user_states[user_id] = {'step': 'ADMIN_INPUT_COINS', 'action': 'set'}
            bot.send_message(message.chat.id, "✏️ Type: <code>User_ID Coins</code>\n(Example: <code>123456789 100</code>)", parse_mode="HTML")

        elif text == "🎁 Change Referral Reward":
            user_states[user_id] = {'step': 'ADMIN_SET_REF'}
            bot.send_message(message.chat.id, "🎁 Har referral par kitne Coins dene hain? Naya number type karke bhejein:")

        elif text == "💲 Edit Service Prices":
            markup = InlineKeyboardMarkup()
            for srv in DEFAULT_PRICES.keys():
                markup.add(InlineKeyboardButton(f"✏️ {srv} ({get_service_price(srv)} Coins)", callback_data=f"editprice_{srv}"))
            bot.send_message(message.chat.id, "🛠️ Jis service ka price change karna hai, uspar click karein:", reply_markup=markup)

        elif text == "📢 Broadcast (Msg for All)":
            user_states[user_id] = {'step': 'ADMIN_BROADCAST_MSG'}
            bot.send_message(message.chat.id, "📢 <b>Message for All Users</b>\n\nJo message sabhi users ko bhejna hai, use yahan type karke send karein:", parse_mode="HTML")

        elif text == "🎟️ Create Redeem Code":
            user_states[user_id] = {'step': 'ADMIN_CREATE_CODE'}
            bot.send_message(message.chat.id, "🎟️ Redeem Code is format me bhejein:\n\n<code>CODE COINS MAX_USERS</code>\n\n<i>Example:</i> <code>OFFER100 50 100</code>", parse_mode="HTML")
        return

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

    elif text == "💳 Buy Play Store Redeem Code":
        price = get_service_price("Play Store Redeem Code")
        user_states[user_id] = {'service': 'Play Store Redeem Code', 'step': 'WAITING_LINK'}
        bot.send_message(
            message.chat.id,
            f"🎁 <b>Play Store Redeem Code Service</b>\n\n"
            f"💡 Price: <code>{price}</code> Coins\n"
            f"🔗 Kripya apna <b>Email Address ya WhatsApp Number</b> bhejein jahan code bheja ja sake:",
            parse_mode="HTML"
        )

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
        bot.send_message(message.chat.id, f"💳 <b>Aapka Balance:</b> <code>{user.get('coins', 0)}</code> Coins\n👥 <b>Total Referrals:</b> <code>{my_refs}</code> Users", parse_mode="HTML")

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

    elif user_id in user_states:
        state = user_states[user_id]
        
        if state['step'] == 'WAITING_REDEEM_CODE':
            code_text = text.strip()
            success, msg = use_redeem_code(user_id, code_text)
            bot.send_message(message.chat.id, msg, parse_mode="HTML")
            del user_states[user_id]

        elif state['step'] == 'WAITING_LINK':
            state['link'] = text
            state['step'] = 'WAITING_QTY'
            unit_price = get_service_price(state['service'])
            min_limit = MIN_ORDER_LIMITS.get(state['service'], 1)
            bot.send_message(message.chat.id, f"🔢 Ab <b>Quantity</b> (sankhya) likhein.\n💡 Rate: <code>{unit_price}</code> Coins per item\n⚠️ <b>Minimum Limit:</b> <code>{min_limit}</code> Quantity Required!", parse_mode="HTML")

        elif state['step'] == 'WAITING_QTY':
            if not text.isdigit():
                bot.send_message(message.chat.id, "❌ Kripya sirf number likhein!")
                return
            
            qty = int(text)
            min_limit = MIN_ORDER_LIMITS.get(state['service'], 1)

            if qty < min_limit:
                bot.send_message(message.chat.id, f"❌ <b>Quantity bohot kam hai!</b>\nIs service me aap <b>{min_limit}</b> se kam ka order nahi laga sakte.", parse_mode="HTML")
                return

            unit_price = get_service_price(state['service'])
            total_cost = qty * unit_price
            
            current_coins = user.get('coins', 0)
            if current_coins < total_cost:
                bot.send_message(
                    message.chat.id, 
                    f"❌ <b>Aapke paas kaafi coins nahi hain!</b>\n\n"
                    f"💳 Total Cost: <code>{total_cost}</code> Coins\n"
                    f"🪙 Aapke Coins: <code>{current_coins}</code> Coins",
                    parse_mode="HTML"
                )
                del user_states[user_id]
                return

            update_coins(user_id, -total_cost)

            bot.send_message(
                message.chat.id,
                f"✅ <b>Order Successfully Placed!</b>\n\n"
                f"📌 <b>Service:</b> {state['service']}\n"
                f"🔗 <b>Target:</b> {state['link']}\n"
                f"🔢 <b>Quantity:</b> {qty}\n"
                f"💰 <b>Total Coins Deducted:</b> {total_cost}\n\n"
                f"🚀 Admin aapka order jald hi complete karega!",
                parse_mode="HTML"
            )

            group_msg = (
                f"🚨 <b>NEW ORDER RECEIVED!</b> 🚨\n\n"
                f"👤 <b>User:</b> @{message.from_user.username or 'No_Username'} (ID: <code>{user_id}</code>)\n"
                f"🛠️ <b>Service:</b> {state['service']}\n"
                f"🔗 <b>Link/Data:</b> <code>{state['link']}</code>\n"
                f"🔢 <b>Quantity:</b> {qty}\n"
                f"💰 <b>Coins Deducted:</b> {total_cost}\n"
                f"📊 <b>Remaining Coins:</b> {current_coins - total_cost}\n\n"
                f"⚡ <i>Kripya is order ko complete karein!</i>"
            )
            try:
                bot.send_message(CHANNELS[0]['username'], group_msg, parse_mode="HTML")
            except Exception:
                bot.send_message(OWNER_ID, f"⚠️ Channel me order msg nahi gaya. Ensure bot Admin ho!\n\n{group_msg}", parse_mode="HTML")

            del user_states[user_id]

        elif state['step'] == 'ADMIN_BROADCAST_MSG':
            broadcast_msg = text
            all_users = get_all_user_ids()
            sent_count = 0
            failed_count = 0
            
            bot.send_message(message.chat.id, f"⏳ Sending broadcast to <code>{len(all_users)}</code> users...", parse_mode="HTML")
            
            for uid in all_users:
                try:
                    bot.send_message(uid, f"📢 <b>Announcement from Admin:</b>\n\n{broadcast_msg}", parse_mode="HTML")
                    sent_count += 1
                    time.sleep(0.05)
                except Exception:
                    failed_count += 1

            bot.send_message(message.chat.id, f"✅ <b>Broadcast Completed!</b>\n\n🎯 Delivered: <code>{sent_count}</code> Users\n❌ Failed/Blocked: <code>{failed_count}</code> Users", parse_mode="HTML")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_CREATE_CODE':
            try:
                parts = text.split()
                code = parts[0].upper()
                coins = int(parts[1])
                max_uses = int(parts[2])
                
                create_redeem_code(code, coins, max_uses)
                bot.send_message(message.chat.id, f"✅ <b>Redeem Code Created Successfully!</b>\n\n🎟️ Code: <code>{code}</code>\n💰 Coins: <code>{coins}</code>\n👥 Max Uses Limit: <code>{max_uses}</code> Users", parse_mode="HTML")
            except Exception:
                bot.send_message(message.chat.id, "❌ Incorrect Format! Use: <code>CODE COINS MAX_USERS</code>", parse_mode="HTML")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_INPUT_COINS':
            try:
                parts = text.split()
                target_user = int(parts[0])
                amount = int(parts[1])
                action = state['action']

                if action == 'add':
                    update_coins(target_user, amount)
                    bot.send_message(message.chat.id, f"✅ <code>{amount}</code> Coins Added to User <code>{target_user}</code>.", parse_mode="HTML")
                elif action == 'remove':
                    update_coins(target_user, -amount)
                    bot.send_message(message.chat.id, f"✅ <code>{amount}</code> Coins Deducted from User <code>{target_user}</code>.", parse_mode="HTML")
                elif action == 'set':
                    set_exact_coins(target_user, amount)
                    bot.send_message(message.chat.id, f"✅ User <code>{target_user}</code> balance set to <code>{amount}</code> Coins.", parse_mode="HTML")

            except Exception:
                bot.send_message(message.chat.id, "❌ Format: <code>User_ID Coins</code>\nExample: <code>123456789 100</code>", parse_mode="HTML")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_CHECK_USER_REF':
            if text.isdigit():
                target_id = int(text)
                u = get_user(target_id)
                if u:
                    c = get_user_referral_count(target_id)
                    ref_by = u.get("referred_by") if u.get("referred_by") else "None (Direct Joined)"
                    bot.send_message(
                        message.chat.id,
                        f"👤 <b>User Details for ID:</b> <code>{target_id}</code>\n\n"
                        f"📛 Username: @{u.get('username')}\n"
                        f"💰 Balance: <code>{u.get('coins', 0)}</code> Coins\n"
                        f"👥 Total Referred: <code>{c}</code> Users\n"
                        f"🔗 Referred By User ID: <code>{ref_by}</code>",
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(message.chat.id, "❌ User database me nahi mila!")
            else:
                bot.send_message(message.chat.id, "❌ Valid User ID enter karein!")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_SET_REF':
            if text.isdigit():
                val = int(text)
                set_setting('referral_reward', val)
                bot.send_message(message.chat.id, f"✅ Referral Reward set to <code>{val}</code> Coins!", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Sirf number type karein!")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_SET_PRICE':
            if text.isdigit():
                val = int(text)
                srv = state['service_to_edit']
                set_setting(f"price_{srv}", val)
                bot.send_message(message.chat.id, f"✅ <b>{srv}</b> price set to <code>{val}</code> Coins per unit!", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Sirf number type karein!")
            del user_states[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv_"))
def process_service_select(call):
    user_id = call.from_user.id
    service_name = call.data.replace("srv_", "")

    user_states[user_id] = {
        'service': service_name,
        'step': 'WAITING_LINK'
    }

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"🎯 Selected Service: <b>{service_name}</b>\n\n"
        f"🔗 Kripya apna <b>Target Link / Username / Details</b> bhejein:",
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv_"))
def process_service_select(call):
    user_id = call.from_user.id
    service_name = call.data.replace("srv_", "")

    user_states[user_id] = {
        'service': service_name,
        'step': 'WAITING_LINK'
    }

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"🎯 Selected Service: <b>{service_name}</b>\n\n"
        f"🔗 Kripya apna <b>Target Link / Username / Details</b> bhejein:",
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("editprice_"))
def process_price_edit_callback(call):
    user_id = call.from_user.id
    if user_id != OWNER_ID:
        return
    srv_name = call.data.replace("editprice_", "")
    user_states[user_id] = {'step': 'ADMIN_SET_PRICE', 'service_to_edit': srv_name}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"💲 <b>{srv_name}</b> ka naya price (Coins) likh kar bhejein:", parse_mode="HTML")

# ==================== MAIN RUNNER ====================
if __name__ == "__main__":
    init_db()
    
    keep_alive()
    print("🌐 Web Server Started for Render 24/7 Hosting!")

    try:
        bot.remove_webhook()
    except Exception:
        pass

    time.sleep(1)

    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"❌ Error occurred: {e}")
            time.sleep(5)

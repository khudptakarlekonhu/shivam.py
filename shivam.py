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

# Verification Channels Details
CHANNELS = [
    {"username": "@ordermonitorbysid", "link": "https://t.me/ordermonitorbysid", "name": "Monitoring Channel"},
    {"username": "@completed_ordersbysid", "link": "https://t.me/completed_ordersbysid", "name": "Completed Orders Channel"}
]

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

# Default Service Prices
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

# Minimum Order Quantity Limits
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
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Add Coins", callback_data="admin_add_coins"), InlineKeyboardButton("➖ Remove Coins", callback_data="admin_remove_coins"))
    markup.add(InlineKeyboardButton("✏️ Set Exact Coins", callback_data="admin_set_coins"), InlineKeyboardButton("📊 Total Users", callback_data="admin_stats"))
    markup.add(InlineKeyboardButton("🏆 Top Referrals", callback_data="admin_top_ref"), InlineKeyboardButton("👥 User Ref Stats", callback_data="admin_user_ref_stats"))
    markup.add(InlineKeyboardButton("🎁 Change Referral Reward", callback_data="admin_set_ref"))
    markup.add(InlineKeyboardButton("💲 Edit Service Prices", callback_data="admin_edit_prices"))
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
            f"⚠️ **Access Denied!**\n\nBot ko use karne ke liye aapko hamare dono official channels ko join karna hoga:\n\n1. {CHANNELS[0]['link']}\n2. {CHANNELS[1]['link']}\n\nJoin karne ke baad **Verify** button dabayein:",
            reply_markup=force_join_markup(),
            parse_mode="Markdown"
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
            f"⚠️ **Access Denied!**\n\nKripya pehle dono channels join karein:",
            reply_markup=force_join_markup(),
            parse_mode="Markdown"
        )
        return

    user = get_user(user_id)
    if not user:
        add_user(user_id, message.from_user.username or message.from_user.first_name)
        user = get_user(user_id)

    text = message.text

    if text == "📸 Instagram":
        bot.send_message(message.chat.id, "👇 **Instagram Services** me se choose karein:", reply_markup=get_instagram_menu(), parse_mode="Markdown")

    elif text == "📘 Facebook":
        bot.send_message(message.chat.id, "👇 **Facebook Services** me se choose karein:", reply_markup=get_facebook_menu(), parse_mode="Markdown")

    elif text == "▶️ YouTube":
        bot.send_message(message.chat.id, "👇 **YouTube Services** me se choose karein:", reply_markup=get_youtube_menu(), parse_mode="Markdown")

    elif text == "💬 WhatsApp":
        bot.send_message(message.chat.id, "👇 **WhatsApp Services** me se choose karein:", reply_markup=get_whatsapp_menu(), parse_mode="Markdown")

    elif text == "✈️ Telegram":
        bot.send_message(message.chat.id, "👇 **Telegram Services** me se choose karein:", reply_markup=get_telegram_menu(), parse_mode="Markdown")

    elif text == "👑 Owner Info":
        msg = f"👑 **Owner / Admin Details**\n\nSupport & Inquiries:\n👉 **Username:** {OWNER_USERNAME}\n👉 **Owner ID:** `{OWNER_ID}`\n👉 **Monitoring:** {CHANNELS[0]['link']}\n👉 **Completed Orders:** {CHANNELS[1]['link']}"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    elif text == "💰 My Balance":
        my_refs = get_user_referral_count(user_id)
        bot.send_message(message.chat.id, f"💳 **Aapka Balance:** `{user[2]}` Coins\n👥 **Total Referrals:** `{my_refs}` Users", parse_mode="Markdown")

    elif text == "🔗 Refer & Earn":
        bot_info = bot.get_me()
        ref_reward = get_setting('referral_reward', 10)
        my_refs = get_user_referral_count(user_id)
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        msg = f"🎁 **Refer & Earn Coins**\n\nApne friends ko invite karein aur har referral par **{ref_reward} Coins** paayein!\n\n👥 Aapke Total Referrals: `{my_refs}` Users\n\nAapka Referral Link:\n`{ref_link}`"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    elif text == "⚙️ Owner Control Panel":
        if user_id == OWNER_ID:
            ref_reward = get_setting('referral_reward', 10)
            bot.send_message(message.chat.id, f"👑 **Welcome Owner!**\n💡 Current Referral Reward: `{ref_reward}` Coins\nNiche se options select karein:", reply_markup=owner_panel_keyboard(), parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Access Denied!")

    elif user_id in user_states:
        state = user_states[user_id]
        
        if state['step'] == 'WAITING_LINK':
            state['link'] = text
            state['step'] = 'WAITING_QTY'
            unit_price = get_service_price(state['service'])
            min_limit = MIN_ORDER_LIMITS.get(state['service'], 10)
            bot.send_message(message.chat.id, f"🔢 Ab **Quantity** (sankhya) likhein.\n💡 Rate: `{unit_price}` Coins per item\n⚠️ **Minimum Limit:** `{min_limit}` Quantity Required!")

        elif state['step'] == 'WAITING_QTY':
            if not text.isdigit():
                bot.send_message(message.chat.id, "❌ Kripya sirf number likhein!")
                return
            
            qty = int(text)
            min_limit = MIN_ORDER_LIMITS.get(state['service'], 10)

            if qty < min_limit:
                bot.send_message(message.chat.id, f"❌ **Quantity bohot kam hai!**\nIs service me aap **{min_limit}** se kam ka order nahi laga sakte.")
                return

            unit_price = get_service_price(state['service'])
            total_cost = qty * unit_price
            
            if user[2] < total_cost:
                bot.send_message(
                    message.chat.id, 
                    f"❌ **Aapke paas kaafi coins nahi hain!**\n\n"
                    f"💳 Total Cost: `{total_cost}` Coins\n"
                    f"🪙 Aapke Coins: `{user[2]}` Coins"
                )
                del user_states[user_id]
                return

            update_coins(user_id, -total_cost)

            bot.send_message(
                message.chat.id,
                f"✅ **Order Successfully Placed!**\n\n"
                f"📌 **Service:** {state['service']}\n"
                f"🔗 **Target:** {state['link']}\n"
                f"🔢 **Quantity:** {qty}\n"
                f"💰 **Total Coins Deducted:** {total_cost}\n\n"
                f"🚀 Admin aapka order jald hi complete karega!"
            )

            group_msg = (
                f"🚨 **NEW ORDER RECEIVED!** 🚨\n\n"
                f"👤 **User:** @{message.from_user.username or 'No_Username'} (ID: `{user_id}`)\n"
                f"🛠️ **Service:** {state['service']}\n"
                f"🔗 **Link/Data:** `{state['link']}`\n"
                f"🔢 **Quantity:** {qty}\n"
                f"💰 **Coins Deducted:** {total_cost}\n"
                f"📊 **Remaining Coins:** {user[2] - total_cost}\n\n"
                f"⚡ *Kripya is order ko complete karein!*"
            )
            try:
                bot.send_message(CHANNELS[0]['username'], group_msg, parse_mode="Markdown")
            except Exception:
                bot.send_message(OWNER_ID, f"⚠️ Channel me order msg nahi gaya. Ensure bot Admin ho!\n\n{group_msg}", parse_mode="Markdown")

            del user_states[user_id]

        elif state['step'] == 'ADMIN_INPUT_COINS':
            try:
                parts = text.split()
                target_user = int(parts[0])
                amount = int(parts[1])
                action = state['action']

                if action == 'add':
                    update_coins(target_user, amount)
                    bot.send_message(message.chat.id, f"✅ `{amount}` Coins Added to User `{target_user}`.")
                elif action == 'remove':
                    update_coins(target_user, -amount)
                    bot.send_message(message.chat.id, f"✅ `{amount}` Coins Deducted from User `{target_user}`.")
                elif action == 'set':
                    set_exact_coins(target_user, amount)
                    bot.send_message(message.chat.id, f"✅ User `{target_user}` balance set to `{amount}` Coins.")

            except Exception:
                bot.send_message(message.chat.id, "❌ Format: `<User_ID> <Coins>`\nExample: `123456789 100`", parse_mode="Markdown")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_CHECK_USER_REF':
            if text.isdigit():
                target_id = int(text)
                u = get_user(target_id)
                if u:
                    c = get_user_referral_count(target_id)
                    ref_by = u[3] if u[3] else "None (Direct Joined)"
                    bot.send_message(
                        message.chat.id,
                        f"👤 **User Details for ID:** `{target_id}`\n\n"
                        f"📛 Username: @{u[1]}\n"
                        f"💰 Balance: `{u[2]}` Coins\n"
                        f"👥 Total Referred: `{c}` Users\n"
                        f"🔗 Referred By User ID: `{ref_by}`",
                        parse_mode="Markdown"
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
                bot.send_message(message.chat.id, f"✅ Referral Reward set to `{val}` Coins!", parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, "❌ Sirf number type karein!")
            del user_states[user_id]

        elif state['step'] == 'ADMIN_SET_PRICE':
            if text.isdigit():
                val = int(text)
                srv = state['service_to_edit']
                set_setting(f"price_{srv}", val)
                bot.send_message(message.chat.id, f"✅ **{srv}** price set to `{val}` Coins per unit!", parse_mode="Markdown")
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
        f"🎯 Selected Service: **{service_name}**\n\n"
        f"🔗 Kripya apna **Target Link / Username / Details** bhejein:",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def process_admin_callbacks(call):
    user_id = call.from_user.id
    if user_id != OWNER_ID:
        bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
        return

    action = call.data.replace("admin_", "")

    if action == "stats":
        total_users = get_total_users_count()
        bot.send_message(call.message.chat.id, f"📊 **Bot Statistics:**\n\n👥 Total Users Joined: `{total_users}`", parse_mode="Markdown")
    
    elif action == "top_ref":
        top_list = get_top_referrals(10)
        if not top_list:
            bot.send_message(call.message.chat.id, "ℹ️ Abhi tak kisi ne referral nahi kiya hai.")
        else:
            msg = "🏆 **Top 10 Referrers List:**\n\n"
            for idx, item in enumerate(top_list, 1):
                u_info = get_user(item[0])
                uname = u_info[1] if u_info else "Unknown"
                msg += f"{idx}. ID: `{item[0]}` (@{uname}) ➔ **{item[1]}** Referrals\n"
            bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    elif action == "user_ref_stats":
        user_states[user_id] = {'step': 'ADMIN_CHECK_USER_REF'}
        bot.send_message(call.message.chat.id, "🔍 Kripya target User ki **Telegram ID** enter karein:")

    elif action in ["add_coins", "remove_coins", "set_coins"]:
        act_type = action.replace("_coins", "")
        user_states[user_id] = {'step': 'ADMIN_INPUT_COINS', 'action': act_type}
        bot.send_message(call.message.chat.id, f"✏️ Type: `User_ID Coins`\n(Example: `123456789 100`)", parse_mode="Markdown")

    elif action == "set_ref":
        user_states[user_id] = {'step': 'ADMIN_SET_REF'}
        bot.send_message(call.message.chat.id, "🎁 Har referral par kitne Coins dene hain? Naya number type karke bhejein:")

    elif action == "edit_prices":
        markup = InlineKeyboardMarkup()
        for srv in DEFAULT_PRICES.keys():
            markup.add(InlineKeyboardButton(f"✏️ {srv} ({get_service_price(srv)} Coins)", callback_data=f"editprice_{srv}"))
        bot.send_message(call.message.chat.id, "🛠️ Jis service ka price change karna hai, uspar click karein:", reply_markup=markup)

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("editprice_"))
def edit_service_price_callback(call):
    user_id = call.from_user.id
    if user_id != OWNER_ID:
        return
    srv_name = call.data.replace("editprice_", "")
    user_states[user_id] = {'step': 'ADMIN_SET_PRICE', 'service_to_edit': srv_name}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"💲 **{srv_name}** ka naya price (Coins) likh kar bhejein:")

# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    init_db()
    print("✅ Database Initialized!")
    
    keep_alive()
    print("🌐 Web Server Started for Render 24/7 Hosting!")

    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"❌ Error occurred: {e}")
            time.sleep(5)
  

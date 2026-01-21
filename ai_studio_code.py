import logging
import asyncio
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import google.generativeai as genai
import sqlite3

# --- Configuration ---
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # BotFather कडून मिळालेला टोकन
GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY'      # Google AI Studio कडून मिळालेली की
ADMIN_ID = 123456789  # तुझा स्वतःचा Telegram ID (userinfobot वरून मिळेल)
QR_IMAGE_PATH = 'payment_qr.jpg'  # तुझ्या पेमेंट QR कोडच्या इमेजचं नाव इथे टाक

# --- Gemini Setup ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Database Setup (SQLite) ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # यूजर टेबल: id, premium status, selected category
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0, category TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- Helper Functions ---
def get_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id):
    if not get_user(user_id):
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

def update_premium(user_id, status):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_premium=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

def update_category(user_id, category):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET category=? WHERE user_id=?", (category, user_id))
    conn.commit()
    conn.close()

# --- AI Question Generator ---
async def generate_question(category):
    topic_prompt = ""
    if category == "law":
        topic_prompt = "MH Law CET 2026 (Legal Aptitude, GK, Logical Reasoning)"
    else:
        topic_prompt = "Maharashtra Police Bharti (Marathi Grammar, GK, Math)"
    
    prompt = f"""
    Create 1 multiple choice question for {topic_prompt}.
    Language: Mix of Marathi and English (Hinglish/Marathi style suitable for Maharashtra students).
    Format: JSON object with keys: 'question', 'options' (list of 4 strings), 'answer_index' (0-3), 'explanation' (1 sentence in Marathi).
    Do not use markdown formatting like ```json. Just raw JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Error generating question: {e}")
        return None

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id)
    
    text = f"नमस्कार {user.first_name}! 👋\nमी तुमचा अभ्यास मित्र आहे. \nकृपया तुमची परीक्षा निवडा:"
    
    keyboard = [
        [InlineKeyboardButton("⚖️ Law CET 2026", callback_data='cat_law')],
        [InlineKeyboardButton("👮 Police Bharti", callback_data='cat_police')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    data = query.data

    # 1. Category Selection
    if data.startswith('cat_'):
        category = data.split('_')[1]
        update_category(user_id, category)
        
        # Check Premium
        user_data = get_user(user_id)
        if user_data[1] == 1: # is_premium
            await send_question(query, context, category)
        else:
            await send_payment_info(query, context)

    # 2. Admin Approval
    elif data.startswith('approve_'):
        target_user_id = int(data.split('_')[1])
        update_premium(target_user_id, 1)
        await context.bot.send_message(chat_id=target_user_id, text="🎉 अभिनंदन! तुमचे पेमेंट Approved झाले आहे. तुम्ही आता Premium Access वापरू शकता. /start वर क्लिक करा.")
        await query.edit_message_caption(caption=f"✅ User {target_user_id} Approved.")

    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        await context.bot.send_message(chat_id=target_user_id, text="❌ तुमचे पेमेंट Rejected झाले आहे. कृपया Admin शी संपर्क करा किंवा पुन्हा प्रयत्न करा.")
        await query.edit_message_caption(caption=f"🚫 User {target_user_id} Rejected.")

    # 3. Quiz Answers
    elif data.startswith('ans_'):
        # data format: ans_correctIndex_selectedIndex
        parts = data.split('_')
        correct_index = int(parts[1])
        selected_index = int(parts[2])
        
        # Retrieve stored question data from context
        q_data = context.user_data.get('current_question')
        
        if not q_data:
            await query.edit_message_text("Session expired. /start again.")
            return

        if selected_index == correct_index:
            await query.edit_message_text(f"🎉 **अगदी बरोबर!** (Correct)\n\n{q_data['explanation']}\n\nपुढचा प्रश्न हवाय?", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("पुढचा प्रश्न ➡️", callback_data=f"next_{context.user_data.get('cat')}")]]))
            # Blast effect logic isn't directly supported via bot API text, but emoji works.
        else:
            keyboard = [
                [InlineKeyboardButton("हो, समजावून सांगा 💡", callback_data='explain')],
                [InlineKeyboardButton("पुढचा प्रश्न ➡️", callback_data=f"next_{context.user_data.get('cat')}")],
            ]
            await query.edit_message_text(f"🚫 **चूक!** (Wrong)\n\nतुम्हाला Explanation पाहिजे का?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'explain':
        q_data = context.user_data.get('current_question')
        await query.edit_message_text(f"💡 **Explanation:**\n{q_data['explanation']}", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("पुढचा प्रश्न ➡️", callback_data=f"next_{context.user_data.get('cat')}")]]))

    elif data.startswith('next_'):
        cat = data.split('_')[1]
        await send_question(query, context, cat)

async def send_payment_info(query, context):
    text = """🚫 **Access Denied!**
    
ही सुविधा फक्त Premium मेंबर्ससाठी आहे.
अभ्यास पूर्ण करण्यासाठी आणि सर्व टेस्ट देण्यासाठी पेमेंट करा.

👇 खालील QR Code स्कॅन करा आणि पेमेंटचा स्क्रीनशॉट इथे पाठवा."""
    
    # QR Code पाठवा (तुमच्या फोल्डरमध्ये 'payment_qr.jpg' नावाची इमेज हवी)
    try:
        await context.bot.send_photo(chat_id=query.from_user.id, photo=open(QR_IMAGE_PATH, 'rb'), caption=text)
    except:
        await query.message.reply_text(f"{text}\n\n(Note to Admin: Please put a 'payment_qr.jpg' file in the bot folder)")

async def handle_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # चेक करा युजरने फोटो पाठवला आहे का
    if update.message.photo:
        # Admin ला फोटो फॉरवर्ड करा
        caption = f"💰 **New Payment Alert!**\nUser: {user.first_name} (ID: {user.id})\nUTR/SS Verify करा."
        
        keyboard = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
        ]
        
        # फोटो Admin ला पाठवा
        file_id = update.message.photo[-1].file_id
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # User ला सांगा
        await update.message.reply_text("⏳ तुमचा स्क्रीनशॉट मिळाला आहे. Admin चेक करून तुम्हाला अप्रूव्हल देतील. थोडी वाट पहा.")

async def send_question(query, context, category):
    # Loading message
    if query.message:
        await query.message.edit_text("🤖 प्रश्न तयार होत आहे... (Generating...) ⏳")
    
    q_data = await generate_question(category)
    
    if not q_data:
        await context.bot.send_message(chat_id=query.from_user.id, text="⚠️ Error generating question. Try again.")
        return

    # Store context for answer checking
    context.user_data['current_question'] = q_data
    context.user_data['cat'] = category

    # Buttons for options
    keyboard = []
    for i, option in enumerate(q_data['options']):
        keyboard.append([InlineKeyboardButton(f"{option}", callback_data=f"ans_{q_data['answer_index']}_{i}")])
    
    text = f"📚 **{category.upper()} Question**\n\n**Q:** {q_data['question']}\n\n⏱️ तुमच्याकडे 1 मिनिट आहे!"
    
    msg = await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # 1 Minute Timer (Background Task)
    asyncio.create_task(timer_task(msg, context))

async def timer_task(message, context):
    await asyncio.sleep(60) # 60 seconds
    try:
        # 60 सेकंदानंतर जर प्रश्न तसाच असेल तर edit करा
        # Note: In a real DB driven app, check if answered. Here simple edit try.
        await message.edit_text("🛑 **Time Up!**\nवेळ संपली आहे. पुढील प्रश्नासाठी /start करा किंवा मागील मेनू वापरा.")
    except Exception:
        pass # जर यूजरने आधीच उत्तर दिलं असेल तर एरर येईल, इग्नोर करा.

# --- Main Execution ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers Add करा
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_payment_screenshot))

    print("Bot is running...")
    app.run_polling()
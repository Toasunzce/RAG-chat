import logging
import os
import time

from dotenv import load_dotenv
import telebot
from telebot import types

from langchain.schema import SystemMessage, HumanMessage, AIMessage

from chat import (
    load_models,
    load_vectorstore,
    generate_response,
    load_file,
    split_documents,
)




# ================== CONFIG ==================


load_dotenv()

messages_history = {}
user_settings = {}
MAX_HISTORY = 5
vectorstore = None

logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

QDRANT_PATH = "./qdrant_storage"
DATA_PATH = "raw_data"


# ================== FUNCTIONS ===============


def get_history(chat_id):
    if chat_id not in messages_history.keys():
        messages_history[chat_id] = [
            SystemMessage(content="You are a helpful AI assistant. Always answer in Russian unless asked otherwise.")
        ]
    return messages_history[chat_id]


def update_history(chat_id, message):
    history = get_history(chat_id)
    history.append(message)
    while len(history) > (2 * MAX_HISTORY + 1):
        history.pop(1)


def get_user_setting(chat_id, key, default=None):
    return user_settings.get(chat_id, {}).get(key, default)


def set_user_setting(chat_id, key, value):
    if chat_id not in user_settings:
        user_settings[chat_id] = {}
    user_settings[chat_id][key] = value


# ================== HANDLERS ===============


@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    if chat_id in messages_history:
        del messages_history[chat_id]

    messages_history[chat_id] = [
        SystemMessage(content="You are a helpful AI assistant. Always answer in Russian unless asked otherwise.")
        ]
    bot.send_message(
        chat_id,
        "👋 Привет! Я бот для вопросов и работы с документами.\n\n"
        "📌 Доступные команды:\n"
        "/ask <вопрос> — задать вопрос\n"
        "/parse — включить или выключить режим парсинга\n"
        "/rag — загрузить текстовый или PDF-файл в базу"
    )


@bot.message_handler(commands=['ask'])
def ask_handler(message):
    chat_id = message.chat.id
    user_text = message.text.replace("/ask", "", 1).strip()

    if not user_text:
        bot.send_message(chat_id, "⚠️ После команды /ask нужно написать сам вопрос.")
        return
    
    update_history(chat_id, HumanMessage(content=user_text))
    history = get_history(chat_id)
    start_time = time.time()
    answer = generate_response(
        vectorstore,
        user_text,
        history,
        parse=get_user_setting(chat_id, "parse", False)
    )
    end_time = time.time()
    logger.info(f"generation time: {round(end_time - start_time, 2)}")
    
    update_history(chat_id, AIMessage(content=answer))

    bot.send_message(chat_id, f"💡 Ответ:\n{answer}")


@bot.message_handler(commands=['parse'])
def parse_handler(message):
    chat_id = message.chat.id
    current = get_user_setting(chat_id, "parse", False)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Включить парсинг", callback_data="parse_on"))
    markup.add(types.InlineKeyboardButton("❌ Выключить парсинг", callback_data="parse_off"))
    bot.send_message(chat_id, f"⚙️ Настройка режима парсинга\nТекущий статус: {current}", reply_markup=markup)



@bot.message_handler(commands=['rag'])
def rag_handler(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "📂 Отправьте .txt или .pdf файл — я добавлю его содержимое в базу знаний.")
    messages_history[chat_id] = [SystemMessage(content="waiting_for_file")]


@bot.message_handler(content_types=['document'])
def document_handler(message):
    chat_id = message.chat.id
    global vectorstore

    history = get_history(chat_id)
    if history and history[0].content == "waiting_for_file":
        file_path = None
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)

            filename = message.document.file_name
            file_path = os.path.join(DATA_PATH, filename)

            with open(file_path, 'wb') as f:
                f.write(downloaded)

            docs = load_file(file_path)
            if not docs:
                bot.send_message(chat_id, "⚠️ Формат файла не поддерживается.")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return

            chunks = split_documents(docs)
            vectorstore.add_documents(chunks)

            logger.info(f"{time.ctime()}: {len(chunks)} chunks from {filename} added")
            bot.send_message(chat_id, f"✅ Файл *{filename}* успешно добавлен в базу ({len(chunks)} фрагмент(ов)).", parse_mode="Markdown")

            messages_history[chat_id] = [
                SystemMessage(content="You are a helpful AI assistant. Always answer in Russian unless asked otherwise.")
            ]

        except Exception as e:
            logger.error(f"Error while handling document: {e}")
            bot.send_message(chat_id, "⚠️ Произошла ошибка при обработке файла.")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    else:
        bot.send_message(chat_id, "ℹ️ Используйте команду /rag перед загрузкой файлов.")


@bot.message_handler(func=lambda message: True)
def message_handler(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "⚠️ Я принимаю только команды. Воспользуйтесь /start, чтобы увидеть список.")


# ============= CALLBACK HANDLERS ===========


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id

    if call.data == "parse_on":
        set_user_setting(chat_id, "parse", True)
        logger.info(f"{time.ctime()}: parsing mode enabled for {chat_id}") 
        bot.send_message(chat_id, "✅ Режим парсинга включён.")

    elif call.data == "parse_off":
        set_user_setting(chat_id, "parse", False)
        logger.info(f"{time.ctime()}: parsing mode disabled for {chat_id}") 
        bot.send_message(chat_id, "❌ Режим парсинга выключен.")


# ================= MAIN LOOP ===============


def main():
    global vectorstore

    logging.basicConfig(
        filename='logs/bot.log',
        level=logging.INFO,
        encoding='utf-8',
        filemode='w'
    )

    logger.info(f"{time.ctime()}: launching process started...") 

    load_models()
    vectorstore = load_vectorstore()

    logger.info(f"{time.ctime()}: bot is up!") 

    bot.infinity_polling()


if __name__ == "__main__":
    main()

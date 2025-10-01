import telebot
from telebot import types
import os
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from chat import load_models, load_vectorstore, generate_response, load_file, split_documents
from dotenv import load_dotenv
import logging 
import shutil
import time
from qdrant_client import QdrantClient

# requirements:
# 1. libmagic
# 2. unstructured
# 3. pypdf
# 4. dotenv



# TODO list DONT SOLVE IT STAIGHTFULLY (must-have first of all)
# 1. concatentate every configs and sublibs into this bot loop
# 2. implement async support. If bot is currently generating response, type "wait till answer!"



# ================== CONFIG ==================


load_dotenv()

messages_history = {}
MAX_HISTORY = 5
vectorstore = None
ENABLE_PARSING = False

logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

QDRANT_PATH = "./qdrant_storage"
DATA_PATH = "raw_data"


# ================== FUNCTIONS ===============


def get_history(chat_id):
    if chat_id not in messages_history.keys():
        messages_history[chat_id] = [SystemMessage(content="...")] # replace with system prompt
    return messages_history[chat_id]


def update_history(chat_id, message):
    history = get_history(chat_id)
    history.append(message)
    while len(history) > (2 * MAX_HISTORY + 1):
        history.pop(1)


# ================== HANDLERS ===============


@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    if chat_id in messages_history:
        del messages_history[chat_id]

    messages_history[chat_id] = [SystemMessage(content='...')] # replace system prompt
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
    answer = generate_response(vectorstore, user_text, history, parse=ENABLE_PARSING)
    end_time = time.time()
    logger.info(f"generation time: {round(end_time - start_time, 2)}")
    
    update_history(chat_id, AIMessage(content=answer))

    bot.send_message(chat_id, f"💡 Ответ:\n{answer}")


@bot.message_handler(commands=['parse'])
def parse_handler(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Включить парсинг", callback_data="parse_on"))
    markup.add(types.InlineKeyboardButton("❌ Выключить парсинг", callback_data="parse_off"))
    bot.send_message(chat_id, f"⚙️ Настройка режима парсинга\nТекущий статус: {ENABLE_PARSING}", reply_markup=markup)


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

            messages_history[chat_id] = [SystemMessage(content="...")]

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
    global ENABLE_PARSING

    if call.data == "parse_on":
        bot.answer_callback_query(call.id)
        ENABLE_PARSING = True
        logger.info(f"{time.ctime()}: parsing mode enabled...") 
        bot.send_message(chat_id, "✅ Режим парсинга включён.")

    elif call.data == "parse_off":
        bot.answer_callback_query(call.id)
        ENABLE_PARSING = False
        logger.info(f"{time.ctime()}: parsing mode disabled") 
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

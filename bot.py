import telebot
from telebot import types
import os
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from chat import load_models, create_vectorstore, load_vectorstore, generate_response
from dotenv import load_dotenv
import logging 
import shutil
from qdrant_client import QdrantClient

# requirements:
# 1. libmagic
# 2. unstructured
# 3. pypdf
# 4. dotenv

# подгрузка и удаление очень медленные. Мб есть более быстрый способ поиска релевантной инфы



# TODO list DONT SOLVE IT STAIGHTFULLY (must-have first of all)
# 1. concatentate every configs and sublibs into this bot loop
# 2. implement async support. If bot is currently generating response, type "wait till answer!"
# 3. REFACTORING
# 4. handle EVERY possible exception (None, ParsingError)



# ================== CONFIG ==================


load_dotenv()

messages_history = {} # every user's chat history
MAX_HISTORY = 5

BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

QDRANT_PATH = "./qdrant_storage"
DATA_PATH = "raw_data"

vectorstore = None
ENABLE_PARSING = False


# =========== FUNCTIONS =============


def get_history(chat_id):
    if chat_id not in messages_history.keys():
        messages_history[chat_id] = [SystemMessage(content="...")] # replace with system prompt
    return messages_history[chat_id]


def update_history(chat_id, message):
    history = get_history(chat_id)
    history.append(message)
    while len(history) > (2 * MAX_HISTORY + 1):
        history.pop(1)


# =========== HANDLERS ==============


@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    if chat_id in messages_history:
        del messages_history[chat_id]

    messages_history[chat_id] = [SystemMessage(content='...')] # replace system prompt
    bot.send_message(chat_id, "Привет! Используй /ask для вопросов. Для настройки режима парсинга используй /parse")


@bot.message_handler(commands=['ask'])
def ask_handler(message):
    chat_id = message.chat.id
    user_text = message.text.replace("/ask", "", 1).strip()

    if not user_text:
        bot.send_message(chat_id, "сначала напиши /ask, а затем свой вопрос!") # replace with "write your question after /ask"
        return
    
    update_history(chat_id, HumanMessage(content=user_text))
    history = get_history(chat_id)

    answer = generate_response(vectorstore, user_text, history, parse=ENABLE_PARSING)
    update_history(chat_id, AIMessage(content=answer))

    bot.send_message(chat_id, answer)


@bot.message_handler(commands=['parse'])
def parse_handler(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("enable parsing", callback_data="parse_on"))
    markup.add(types.InlineKeyboardButton("disable parsing"), callback_data="parse_off")
    bot.send_message(chat_id, "enable parse mode?", reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def message_handler(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "используй только команды!") # replace with warning like "use list of commands instead of stuped typing idiot"


# =========== CALLBACK HANDLER  ==============


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    global ENABLE_PARSING

    if call.data == "parse_on":
        bot.answer_callback_query(call.id)
        ENABLE_PARSING = True

    elif call.data == "parse_off":
        bot.answer_callback_query(call.id)
        ENABLE_PARSING = False


# =========== MAIN LOOP ==============


def main():
    global vectorstore

    load_models()
    print("llm & emb are loaded")
    vectorstore = load_vectorstore()
    print("vectorstore loaded")
    bot.infinity_polling()




if __name__ == "__main__":
    main()

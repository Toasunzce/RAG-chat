# Info

Solution to the test case for "AI-bot developer" intership at [Sberbank](https://www.sberbank.ru/)

The goal of the project is to build an AI-based telegram application for handilng LLM conversations with RAG and parsing tools.

# Structure

The telegram bot is based on LLM **LLaMA 3.3 Versatile** (70B params), ported via **Groq API**. This model provides conversations in russian and is used to generate responses to the user. 

To improve the quality of response, the system was integrated with **RAG-tools** and **vectorstores** (Qdrant). Documents uploaded to the system are encrypted into embeddings using **ru-en-RoSBERTa**, ported via [Hugging Face](https://huggingface.co/ai-forever/ru-en-RoSBERTa). A web-parsing module was also implemented, allowing data to be extracted from the internet and taken into account when generating a response.

*The complite diagram of the system is presented below.*
![diagram](bot_scheme.jpg)

# Supported commands

| command | description |
|--------|-------|
| /start | list of the commands and bot description |
| /ask <que> | ask a question to the bot |
| /parse | enable/disable parsing from the web |
| /rag | add documents to the database (.txt, .md or .pdf) |

# How to use

1. Register a new bot using [@BotFather] and get the token
2. Create `.env` file and paste your tokens in the sections below:
```
GROQ_API_KEY=
BOT_TOKEN=
```
3. Select necessary requariments using
```bash
cd constellation-recognition
pip install -r requirements.txt
```
4. And run `bot.py` module:
```bash
python bot.py
```





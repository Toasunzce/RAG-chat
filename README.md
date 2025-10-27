# Info

Solution to the test case for еру "AI-bot developer" intership at [Sberbank](https://www.sberbank.ru/). Goal: build a Telegram bot powered by a large language model with Russian dialogue, Retrieval‑Augmented Generation (RAG) over user documents, and a web‑parsing module to incorporate fresh information into answers.
The core application logic (LLM, templates, RAG pipeline) is built on LangChain.

## Structure

The telegram bot is based on LLM **LLaMA 3.3 Versatile** (70B params), ported via **Groq API**. This model provides conversations in russian and is used to generate responses to the user. 

To improve the quality of response, the system was integrated with **RAG-tools** and **vectorstores** (Qdrant). Documents uploaded to the system are encrypted into embeddings using **ru-en-RoSBERTa**, ported via [Hugging Face](https://huggingface.co/ai-forever/ru-en-RoSBERTa). A web-parsing module was also implemented, allowing data to be extracted from the internet and taken into account when generating a response.

*System diagram*

<img src="content/bot_scheme.jpg" width=60% height=60%>

## Supported commands

| command | description |
|--------|-------|
| /start | bot description and command list |
| /ask <que> | ask the bot |
| /parse | enable/disable parsing from the web |
| /rag | upload documents to the knowledge base (.txt, .md, .pdf) |

# Getting Started

1. Register a new telegram bot using [@BotFather] and obtain the token
2. Create a `.env` file and paste your tokens in the sections below:
```
GROQ_API_KEY=
BOT_TOKEN=
```
3. Install dependencies
```bash
cd constellation-recognition
pip install -r requirements.txt
```
4. And run the `bot.py` module:
```bash
python bot.py
```

## Usage example

<img src="content/screen.png" width=40% height=40%>

## Roadmap

- Add multiprocessing
- Optimize data extraction from vectorstore (relevance score, reranker)
- Organize documents by users
- Implement automatic storage
- UI/UX upgrade (mini-app)
- Local LLM

## Troubleshooting

- When multiple users are using requests, the bot crashes
- Many users has shared storage. This can easily cause dataleaks
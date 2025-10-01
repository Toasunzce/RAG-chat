import logging
import os
import time
import uuid

from dotenv import load_dotenv

from langchain.schema import Document, HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from parser import parse_info




# ================== CONFIG ==================


load_dotenv()

DATA_PATH = "raw_data"
QDRANT_PATH = "./qdrant_storage"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = None
embedder = None
logger = logging.getLogger(__name__)

# ================== MODELS ==================


def load_models():
    global llm, embedder
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile"
    )
    embedder = HuggingFaceEmbeddings(model_name="ai-forever/ru-en-RoSBERTa")
    if llm and embedder:
        logger.info(f"{time.ctime()}: llm and embedder loaded")                 # logs
    # installing in %USERPROFILE%\.cache\huggingface\hub\


# ================== DOCUMENTS ==================


def load_documents():
    documents = []

    txt_loader = DirectoryLoader(
        DATA_PATH,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    documents.extend(txt_loader.load())

    md_loader = DirectoryLoader(
        DATA_PATH,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    documents.extend(md_loader.load())

    pdf_loader = DirectoryLoader(
        DATA_PATH,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader
    )
    documents.extend(pdf_loader.load())

    return documents


def load_file(filepath):
    loader = None
    if ".md" in filepath or ".txt" in filepath:
        loader = TextLoader(filepath, encoding="utf-8")
    elif ".pdf" in filepath:
        loader = PyPDFLoader(filepath)
    else:
        return None
    documents = loader.load()
    return documents


def split_documents(documents: list[Document]):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
        length_function=len,
        add_start_index=True
    )
    return splitter.split_documents(documents)


# ================== VECTORSTORE ==================


def create_vectorstore():
    documents = load_documents()
    chunks = split_documents(documents)

    vectorstore = QdrantVectorStore.from_documents(
        chunks,
        embedding=embedder,
        path=QDRANT_PATH,
        collection_name="docs"
    )
    logger.info(f"{time.ctime()}: {len(chunks)} chunks loaded into store")      # logs
    return vectorstore


def load_vectorstore():
    client = QdrantClient(path=QDRANT_PATH)
    vectorstore =  QdrantVectorStore(
        client=client,
        collection_name="docs",
        embedding=embedder
    )
    logger.info(f"{time.ctime()}: store loaded")                                # logs
    return vectorstore


def search_docs(vectorstore, query, k=5):
    return vectorstore.similarity_search(query, k=k)


def add_parsed_text_to_db(vectorstore, text, source_name="parser"):
    document = Document(page_content=text, metadata={"source": source_name})
    chunks = split_documents([document])
    vectorstore.add_documents(chunks)
    logger.info(f"{time.ctime()}: {len(chunks)} web chunks added into store")   # logs


def delete_via_source(vectorstore, source_name="parser"):
    client = vectorstore.client
    collection_name = vectorstore.collection_name

    delete_filter = Filter(
        must=[FieldCondition(
            key="metadata.source",
            match=MatchValue(value=source_name)
        )]
    )
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=delete_filter
        )
        logger.info(f"{time.ctime()}: parsed docs deleted")                     # logs
    except Exception as e:
        print(f"error deleting docs with source={source_name}: {e}")
        logger.info(                                                            # logs
            f"{time.ctime()}: error deleting docs with source={source_name}: {e}"
        )


# ================== RESPONSE ==================


def generate_response(vectorstore, question, history, parse=True):
    temp_source = None

    if parse:
        temp_source = f"parser_{uuid.uuid4().hex}"
        parsed_info = parse_info(question)
        add_parsed_text_to_db(vectorstore, parsed_info, source_name=temp_source)

    docs = search_docs(vectorstore, question)
    context = "\n\n".join([doc.page_content for doc in docs])

    if parse and temp_source:
        delete_via_source(vectorstore, source_name=temp_source)

    template = f"""
    Answer the question using relevant context below:

    Context:
    {context}

    Question:
    {question}

    Give an accurate answer based on this context.
    Otherwise answer using your own knowledge.
    """

    prompt_template = ChatPromptTemplate.from_template(template)
    formatted_prompt = prompt_template.format(context=context, question=question)

    messages = history + [HumanMessage(content=formatted_prompt)]
    response = llm.invoke(messages)
    
    logger.info(f"{time.ctime()}: response generated")                          # logs

    return response.content


# ================== MAIN ==================


if __name__ == "__main__":
    load_models()
    vectorstore = create_vectorstore()
import os
import json
import time

from typing import TypedDict, List, Dict, Any

from dotenv import load_dotenv

import psycopg
from pgvector.psycopg import register_vector

from openai import OpenAI

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langgraph.graph import StateGraph, START, END


# ============================================================
# CONFIGURAÇÕES
# ============================================================

load_dotenv()


# ============================================================
# OPENAI
#
# Usado SOMENTE para gerar embeddings
# ============================================================

openai_key = os.getenv("OPENAI_API_KEY")

if not openai_key:
    raise ValueError(
        "OPENAI_API_KEY não foi encontrada no arquivo .env"
    )


openai_client = OpenAI(
    api_key=openai_key
)


# ============================================================
# OPENROUTER
#
# Usado para a LLM
# ============================================================

openrouter_key = os.getenv("OPENROUTER_API_KEY")

if not openrouter_key:
    raise ValueError(
        "OPENROUTER_API_KEY não foi encontrada no arquivo .env"
    )


llm_client = OpenAI(
    api_key=openrouter_key,
    base_url="https://openrouter.ai/api/v1"
)


# ============================================================
# MODELO DA LLM
# ============================================================

LLM_MODEL = "google/gemini-2.5-flash"


# ============================================================
# MODELO DE EMBEDDING
# ============================================================

EMBEDDING_MODEL = "text-embedding-3-small"

EMBEDDING_DIMENSIONS = 1536


# ============================================================
# CONFIGURAÇÃO DO BANCO
# ============================================================

DB_URI = os.getenv("DB_URI")

if not DB_URI:
    raise ValueError(
        "DB_URI não foi encontrada no arquivo .env"
    )


print()
print("========================================")
print("CONECTANDO AO POSTGRESQL")
print("========================================")


conn = psycopg.connect(
    DB_URI,
    autocommit=True
)


print(
    "PostgreSQL conectado com sucesso!"
)


# ============================================================
# CONFIGURAR PGVECTOR
# ============================================================

conn.execute(
    "CREATE EXTENSION IF NOT EXISTS vector;"
)

register_vector(conn)


print(
    "pgvector configurado com sucesso!"
)


# ============================================================
# CRIAR / CORRIGIR TABELA ARTICLES
# ============================================================

print()
print("========================================")
print("CONFIGURANDO TABELA ARTICLES")
print("========================================")


conn.execute(
    """
    CREATE TABLE IF NOT EXISTS articles (
        id VARCHAR(255) PRIMARY KEY,
        titulo TEXT,
        texto TEXT NOT NULL,
        metadata JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
)


# ============================================================
# GARANTIR QUE AS COLUNAS EXISTAM
#
# Isso corrige o problema:
#
# psycopg.errors.UndefinedColumn:
# coluna a.titulo não existe
# ============================================================

conn.execute(
    """
    ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS titulo TEXT;
    """
)


conn.execute(
    """
    ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS texto TEXT;
    """
)


conn.execute(
    """
    ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS metadata JSONB;
    """
)


conn.execute(
    """
    ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP
    DEFAULT CURRENT_TIMESTAMP;
    """
)


print(
    "Tabela articles configurada!"
)


# ============================================================
# CRIAR / CORRIGIR TABELA ARTICLE_CHUNKS
# ============================================================

print()
print("========================================")
print("CONFIGURANDO TABELA ARTICLE_CHUNKS")
print("========================================")


conn.execute(
    """
    CREATE TABLE IF NOT EXISTS article_chunks (
        id BIGSERIAL PRIMARY KEY,

        article_id VARCHAR(255) NOT NULL,

        chunk_index INTEGER NOT NULL,

        text TEXT NOT NULL,

        embedding VECTOR(1536) NOT NULL,

        CONSTRAINT fk_article
            FOREIGN KEY (article_id)
            REFERENCES articles(id)
            ON DELETE CASCADE,

        CONSTRAINT unique_article_chunk
            UNIQUE (article_id, chunk_index)
    );
    """
)


# ============================================================
# GARANTIR COLUNAS DO ARTICLE_CHUNKS
# ============================================================

conn.execute(
    """
    ALTER TABLE article_chunks
    ADD COLUMN IF NOT EXISTS article_id VARCHAR(255);
    """
)


conn.execute(
    """
    ALTER TABLE article_chunks
    ADD COLUMN IF NOT EXISTS chunk_index INTEGER;
    """
)


conn.execute(
    """
    ALTER TABLE article_chunks
    ADD COLUMN IF NOT EXISTS text TEXT;
    """
)


conn.execute(
    """
    ALTER TABLE article_chunks
    ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);
    """
)


print(
    "Tabela article_chunks configurada!"
)


# ============================================================
# ÍNDICE DO PGVECTOR
# ============================================================

print()
print("========================================")
print("CONFIGURANDO ÍNDICE PGVECTOR")
print("========================================")


conn.execute(
    """
    CREATE INDEX IF NOT EXISTS
    article_chunks_embedding_idx
    ON article_chunks
    USING hnsw (embedding vector_cosine_ops);
    """
)


print(
    "Índice HNSW configurado!"
)


# ============================================================
# ESTADO DO LANGGRAPH
# ============================================================

class GraphState(TypedDict):

    question: str

    relevant_chunks: List[Dict[str, Any]]

    answer: str


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="RAG G1 API",
    description="RAG com LangGraph, PostgreSQL, PGVector e OpenRouter",
    version="1.0.0"
)


# ============================================================
# MODELOS DA API
# ============================================================

class ChatMessage(BaseModel):

    role: str

    content: str


class ChatCompletionRequest(BaseModel):

    model: str = "rag-g1"

    messages: List[ChatMessage]


# ============================================================
# DIVIDIR TEXTO EM CHUNKS
# ============================================================

def split_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        if chunk.strip():

            chunks.append(chunk)

        start = end - chunk_overlap

    return chunks


# ============================================================
# GERAR EMBEDDING
# ============================================================

def get_openai_embedding(text: str):

    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )

    return response.data[0].embedding


# ============================================================
# VERIFICAR SE NOTÍCIA EXISTE
# ============================================================

def article_exists(article_id):

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT 1
            FROM articles
            WHERE id = %s
            LIMIT 1;
            """,
            (article_id,)
        )

        return cur.fetchone() is not None


# ============================================================
# INDEXAR NOTÍCIA
# ============================================================

def index_article(article):

    article_id = article["id"]

    metadata = article.get(
        "metadata",
        {}
    )

    titulo = metadata.get(
        "titulo",
        ""
    )

    texto = article.get(
        "texto",
        ""
    )


    if not texto or not texto.strip():

        print(
            f"Notícia {article_id} não possui texto."
        )

        return


    # ========================================================
    # VERIFICAR SE A NOTÍCIA JÁ EXISTE
    # ========================================================

    if article_exists(article_id):

        print(
            f"Notícia já existe: {article_id}"
        )

        return


    print()
    print(
        f"Nova notícia: {article_id}"
    )

    print(
        f"Título: {titulo}"
    )


    # ========================================================
    # SALVAR NOTÍCIA ORIGINAL
    # ========================================================

    conn.execute(
        """
        INSERT INTO articles (
            id,
            titulo,
            texto,
            metadata
        )
        VALUES (
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (id)
        DO NOTHING;
        """,
        (
            article_id,
            titulo,
            texto,
            json.dumps(metadata)
        )
    )


    # ========================================================
    # DIVIDIR NOTÍCIA EM CHUNKS
    # ========================================================

    chunks = split_text(
        texto
    )


    print(
        f"Total de chunks: {len(chunks)}"
    )


    # ========================================================
    # GERAR EMBEDDINGS
    # ========================================================

    for chunk_index, chunk in enumerate(chunks):

        print(
            f"Gerando embedding "
            f"{chunk_index + 1}/{len(chunks)}..."
        )


        embedding = get_openai_embedding(
            chunk
        )


        # ====================================================
        # SALVAR CHUNK
        # ====================================================

        conn.execute(
            """
            INSERT INTO article_chunks (
                article_id,
                chunk_index,
                text,
                embedding
            )
            VALUES (
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (
                article_id,
                chunk_index
            )
            DO NOTHING;
            """,
            (
                article_id,
                chunk_index,
                chunk,
                embedding
            )
        )


    print(
        f"Notícia {article_id} indexada com sucesso!"
    )


# ============================================================
# CARREGAR JSON
# ============================================================

def load_documents_from_json(json_path):

    print()
    print(
        "========================================"
    )

    print(
        "CARREGANDO NOTÍCIAS DO JSON"
    )

    print(
        "========================================"
    )


    with open(
        json_path,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)


    print(
        f"{len(data)} notícias encontradas."
    )


    return data


# ============================================================
# INDEXAR DOCUMENTOS
# ============================================================

def index_documents(documents):

    print()
    print(
        "========================================"
    )

    print(
        "INICIANDO INDEXAÇÃO"
    )

    print(
        "========================================"
    )


    for article in documents:

        try:

            index_article(
                article
            )

        except Exception as e:

            print()
            print(
                "ERRO AO INDEXAR NOTÍCIA:"
            )

            print(
                e
            )

            print(
                f"ID da notícia: "
                f"{article.get('id', 'desconhecido')}"
            )


    print()
    print(
        "========================================"
    )

    print(
        "INDEXAÇÃO FINALIZADA"
    )

    print(
        "========================================"
    )


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve_documents(
    state: GraphState
):

    question = state["question"]


    print()
    print(
        "[LANGGRAPH] retrieve_documents"
    )


    # ========================================================
    # EMBEDDING DA PERGUNTA
    # ========================================================

    query_embedding = get_openai_embedding(
        question
    )


    # ========================================================
    # BUSCAR CHUNKS
    # ========================================================

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT

                ac.id,

                ac.article_id,

                ac.chunk_index,

                ac.text,

                ac.embedding <=> %s::vector
                    AS distance,

                1 - (
                    ac.embedding <=> %s::vector
                )
                    AS similarity,

                a.titulo,

                a.metadata,

                a.texto

            FROM article_chunks ac

            INNER JOIN articles a
                ON a.id = ac.article_id

            ORDER BY
                ac.embedding <=> %s::vector

            LIMIT 5;
            """,
            (
                query_embedding,
                query_embedding,
                query_embedding
            )
        )


        rows = cur.fetchall()


    relevant_chunks = []


    # ========================================================
    # ORGANIZAR RESULTADOS
    # ========================================================

    for row in rows:

        relevant_chunks.append({

            "chunk_id": row[0],

            "article_id": row[1],

            "chunk_index": row[2],

            "text": row[3],

            "distance": row[4],

            "similarity": row[5],

            "titulo": row[6],

            "metadata": row[7] or {},

            "article_text": row[8]

        })


    print(
        f"Chunks recuperados: "
        f"{len(relevant_chunks)}"
    )


    # ========================================================
    # MOSTRAR RESULTADOS DO RETRIEVAL
    # ========================================================

    for i, chunk in enumerate(
        relevant_chunks,
        start=1
    ):

        print()
        print(
            f"Documento {i}"
        )

        print(
            f"Título: {chunk['titulo']}"
        )

        print(
            f"Similaridade: "
            f"{chunk['similarity']:.4f}"
        )


    return {

        "relevant_chunks":
            relevant_chunks

    }


# ============================================================
# GERAR RESPOSTA
# ============================================================

def generate_response(
    state: GraphState
):

    question = state["question"]

    relevant_chunks = state[
        "relevant_chunks"
    ]


    print()
    print(
        "[LANGGRAPH] generate_response"
    )


    # ========================================================
    # CASO NÃO ENCONTRE DOCUMENTOS
    # ========================================================

    if not relevant_chunks:

        return {

            "answer":
                "Não encontrei informações suficientes "
                "nas notícias disponíveis para responder "
                "à pergunta."

        }


    # ========================================================
    # CONSTRUIR CONTEXTO
    # ========================================================

    context_parts = []


    for i, chunk in enumerate(
        relevant_chunks,
        start=1
    ):

        metadata = chunk.get(
            "metadata",
            {}
        )


        titulo = chunk.get(
            "titulo",
            ""
        )


        data = metadata.get(
            "data",
            ""
        )


        url = metadata.get(
            "url",
            ""
        )


        source_info = ""


        if titulo:

            source_info += (
                f"Título: {titulo}\n"
            )


        if data:

            source_info += (
                f"Data: {data}\n"
            )


        if url:

            source_info += (
                f"URL: {url}\n"
            )


        context_parts.append(
            f"""
--- TRECHO {i} ---

{source_info}

Conteúdo do trecho:

{chunk["text"]}

Similaridade:

{chunk["similarity"]:.4f}
"""
        )


    context = "\n".join(
        context_parts
    )


    # ========================================================
    # PROMPT
    # ========================================================

    prompt = f"""
Você é um assistente especializado em análise
e explicação de notícias.

O modelo utilizado para gerar a resposta é:

{LLM_MODEL}

Sua função é responder às perguntas do usuário
como um jornalista experiente.

Apresente as informações de maneira:

- clara;
- detalhada;
- objetiva;
- contextualizada;
- informativa.

REGRAS FUNDAMENTAIS:

1. Utilize SOMENTE as informações presentes
   nos trechos fornecidos.

2. NÃO invente fatos.

3. NÃO invente nomes.

4. NÃO invente datas.

5. NÃO invente números.

6. NÃO invente acontecimentos.

7. Não considere uma afirmação verdadeira
   simplesmente porque ela aparece na pergunta.

8. Se os documentos não tiverem informações
   suficientes para responder à pergunta,
   informe claramente essa limitação.

9. Diferencie fatos relatados nos documentos
   de interpretações.

10. Quando houver informações conflitantes
    entre os trechos, apresente a divergência.

11. Não invente informações para preencher
    lacunas.

12. Não diga que realizou uma busca na internet.

13. Baseie a resposta exclusivamente no contexto
    fornecido.

14. Sempre mostre a fonte da notícia quando
    houver URL disponível.

15. Sempre informe a data da notícia no início
    da resposta quando a data estiver disponível.

16. Se houver várias notícias sobre o mesmo
    acontecimento, utilize as informações
    complementares entre elas.

17. Não confunda uma notícia que desmente
    determinado fato com uma notícia que afirma
    que o fato aconteceu.

18. Se a pergunta pressupuser que determinado
    acontecimento ocorreu, verifique essa
    afirmação somente com base nos documentos.

CONTEXTO DOS DOCUMENTOS:

{context}

PERGUNTA DO USUÁRIO:

{question}

Responda como um jornalista apresentando
uma informação ao público.
"""


    # ========================================================
    # OPENROUTER
    # ========================================================

    print()
    print(
        f"[OPENROUTER] Modelo: {LLM_MODEL}"
    )


    response = llm_client.chat.completions.create(

        model=LLM_MODEL,

        messages=[

            {
                "role": "system",
                "content": prompt
            },

            {
                "role": "user",
                "content": question
            }

        ]

    )


    answer = (
        response
        .choices[0]
        .message
        .content
    )


    return {

        "answer": answer

    }


# ============================================================
# CONSTRUIR LANGGRAPH
# ============================================================

workflow = StateGraph(
    GraphState
)


workflow.add_node(
    "retrieve_documents",
    retrieve_documents
)


workflow.add_node(
    "generate_response",
    generate_response
)


workflow.add_edge(
    START,
    "retrieve_documents"
)


workflow.add_edge(
    "retrieve_documents",
    "generate_response"
)


workflow.add_edge(
    "generate_response",
    END
)


graph = workflow.compile()


# ============================================================
# ENDPOINT DE TEST
# ============================================================

@app.get("/")
def root():

    return {

        "status": "online",

        "service": "RAG G1",

        "model": LLM_MODEL,

        "embedding_model":
            EMBEDDING_MODEL

    }


# ============================================================
# ENDPOINT /V1/MODELS
#
# Necessário para clientes compatíveis com OpenAI,
# incluindo Open WebUI.
# ============================================================

@app.get("/v1/models")
def list_models():

    return {

        "object": "list",

        "data": [

            {

                "id": "rag-g1",

                "object": "model",

                "created": int(
                    time.time()
                ),

                "owned_by": "rag-g1"

            }

        ]

    }


# ============================================================
# ENDPOINT OPENAI COMPATIBLE
#
# OPEN WEBUI UTILIZARÁ ESTE ENDPOINT
# ============================================================

@app.post(
    "/v1/chat/completions"
)
def chat_completions(
    request: ChatCompletionRequest
):

    try:

        # ====================================================
        # PEGAR A ÚLTIMA MENSAGEM DO USUÁRIO
        # ====================================================

        question = ""


        for message in reversed(
            request.messages
        ):

            if message.role == "user":

                question = message.content

                break


        if not question:

            raise HTTPException(
                status_code=400,
                detail="Nenhuma pergunta do usuário foi encontrada."
            )


        print()
        print(
            "========================================"
        )

        print(
            "NOVA PERGUNTA"
        )

        print(
            question
        )

        print(
            "========================================"
        )


        # ====================================================
        # EXECUTAR LANGGRAPH
        # ====================================================

        result = graph.invoke(

            {

                "question":
                    question,

                "relevant_chunks":
                    [],

                "answer":
                    ""

            }

        )


        answer = result[
            "answer"
        ]


        # ====================================================
        # FORMATO COMPATÍVEL COM OPENAI
        # ====================================================

        return {

            "id":
                "rag-g1-completion",

            "object":
                "chat.completion",

            "created":
                int(
                    time.time()
                ),

            "model":
                "rag-g1",

            "choices": [

                {

                    "index":
                        0,

                    "message": {

                        "role":
                            "assistant",

                        "content":
                            answer

                    },

                    "finish_reason":
                        "stop"

                }

            ]

        }


    except HTTPException:

        raise


    except Exception as e:

        print()
        print(
            "========================================"
        )

        print(
            "ERRO NO RAG"
        )

        print(
            "========================================"
        )

        print(
            repr(e)
        )

        print(
            "========================================"
        )


        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# ============================================================
# EXECUTAR API
# ============================================================

if __name__ == "__main__":

    import uvicorn


    print()
    print(
        "========================================"
    )

    print(
        "RAG G1 API"
    )

    print(
        "========================================"
    )

    print(
        f"LLM: {LLM_MODEL}"
    )

    print(
        f"Embedding: {EMBEDDING_MODEL}"
    )

    print(
        "API: http://localhost:8000"
    )

    print()
    print(
        "Endpoints:"
    )

    print(
        "GET  http://localhost:8000/"
    )

    print(
        "GET  http://localhost:8000/v1/models"
    )

    print(
        "POST http://localhost:8000/v1/chat/completions"
    )

    print(
        "========================================"
    )


    # ========================================================
    # INDEXAÇÃO
    # ========================================================

    json_path = "./news_articles.json"


    if os.path.exists(
        json_path
    ):

        documents = (
            load_documents_from_json(
                json_path
            )
        )


        index_documents(
            documents
        )

    else:

        print(
            f"Arquivo {json_path} não encontrado."
        )


    # ========================================================
    # INICIAR FASTAPI
    # ========================================================

    uvicorn.run(

        app,

        host="0.0.0.0",

        port=8000

    )
# import os
# import json

# from dotenv import load_dotenv
# import psycopg
# from pgvector.psycopg import register_vector
# from openai import OpenAI

# from langgraph.graph import StateGraph, START, END
# from typing import TypedDict, List, Dict, Any


# # ============================================================
# # CONFIGURAÇÕES
# # ============================================================

# load_dotenv()

# # ============================================================
# # CHAVE DA OPENAI
# # USADA SOMENTE PARA EMBEDDINGS
# # ============================================================

# openai_key = os.getenv("OPENAI_API_KEY")

# if not openai_key:
#     raise ValueError(
#         "OPENAI_API_KEY não foi encontrada no arquivo .env"
#     )


# # Cliente OpenAI
# # Usado para gerar os embeddings das notícias
# openai_client = OpenAI(
#     api_key=openai_key
# )


# # ============================================================
# # CHAVE DO OPENROUTER
# # USADA PARA A LLM
# # ============================================================

# openrouter_key = os.getenv("OPENROUTER_API_KEY")

# if not openrouter_key:
#     raise ValueError(
#         "OPENROUTER_API_KEY não foi encontrada no arquivo .env"
#     )


# # Cliente OpenRouter
# #
# # O OpenRouter possui API compatível com o SDK da OpenAI.
# # Basta alterar o base_url.
# #
# # Documentação:
# # https://openrouter.ai/
# # ============================================================

# llm_client = OpenAI(
#     api_key=openrouter_key,
#     base_url="https://openrouter.ai/api/v1"
# )


# # ============================================================
# # MODELO DA LLM
# # ============================================================

# LLM_MODEL = "google/gemini-2.5-flash"


# # ============================================================
# # CONEXÃO COM POSTGRESQL
# # ============================================================

# DB_URI = os.getenv("DB_URI")

# if not DB_URI:
#     raise ValueError(
#         "DB_URI não foi encontrada no arquivo .env"
#     )


# print(
#     "\n==== Conectando ao PostgreSQL ===="
# )

# conn = psycopg.connect(
#     DB_URI,
#     autocommit=True
# )

# print(
#     "PostgreSQL conectado com sucesso!"
# )


# # ============================================================
# # CONFIGURAR PGVECTOR
# # ============================================================

# conn.execute(
#     "CREATE EXTENSION IF NOT EXISTS vector;"
# )

# register_vector(conn)

# print(
#     "pgvector configurado com sucesso!"
# )


# # ============================================================
# # CRIAR TABELA
# # ============================================================

# conn.execute("""
# CREATE TABLE IF NOT EXISTS document_qa_collection (
#     id VARCHAR(255) PRIMARY KEY,
#     text TEXT,
#     metadata JSONB,
#     embedding vector(1536)
# );
# """)

# print(
#     "Tabela document_qa_collection pronta!"
# )


# # ============================================================
# # ESTADO DO LANGGRAPH
# # ============================================================

# class GraphState(TypedDict):

#     question: str

#     relevant_chunks: List[Dict[str, Any]]

#     answer: str


# # ============================================================
# # CARREGAR DOCUMENTOS DO JSON
# # ============================================================

# def load_documents_from_json(json_path):

#     print(
#         "\n==== Verificando arquivo JSON ===="
#     )

#     with open(
#         json_path,
#         "r",
#         encoding="utf-8"
#     ) as file:

#         data = json.load(file)

#     documents = []

#     for article in data:

#         titulo = article.get(
#             "metadata",
#             {}
#         ).get(
#             "titulo",
#             ""
#         )

#         texto = article.get(
#             "texto",
#             ""
#         )

#         conteudo = (
#             f"{titulo}\n\n{texto}"
#         )

#         documents.append({
#             "id": article["id"],
#             "text": conteudo,
#             "metadata": article.get(
#                 "metadata",
#                 {}
#             )
#         })

#     return documents


# # ============================================================
# # DIVIDIR TEXTO EM CHUNKS
# # ============================================================

# def split_text(
#     text,
#     chunk_size=1000,
#     chunk_overlap=200
# ):

#     chunks = []

#     start = 0

#     while start < len(text):

#         end = start + chunk_size

#         chunks.append(
#             text[start:end]
#         )

#         start = end - chunk_overlap

#     return chunks


# # ============================================================
# # GERAR EMBEDDING
# #
# # IMPORTANTE:
# # Continua sendo OpenAI.
# # A LLM de resposta é que foi transferida para OpenRouter.
# # ============================================================

# def get_openai_embedding(text):

#     response = openai_client.embeddings.create(
#         input=text,
#         model="text-embedding-3-small"
#     )

#     return response.data[0].embedding


# # ============================================================
# # VERIFICAR SE CHUNK JÁ EXISTE
# # ============================================================

# def chunk_exists(chunk_id):

#     with conn.cursor() as cur:

#         cur.execute(
#             """
#             SELECT 1
#             FROM document_qa_collection
#             WHERE id = %s
#             LIMIT 1;
#             """,
#             (chunk_id,)
#         )

#         return cur.fetchone() is not None


# # ============================================================
# # INDEXAR SOMENTE NOVOS DOCUMENTOS
# # ============================================================

# def index_documents(documents):

#     print(
#         "\n==== Verificando documentos existentes ===="
#     )

#     total_chunks = 0

#     new_chunks = 0

#     existing_chunks = 0


#     for doc in documents:

#         chunks = split_text(
#             doc["text"]
#         )


#         for i, chunk in enumerate(chunks):

#             total_chunks += 1

#             chunk_id = (
#                 f"{doc['id']}_chunk_{i}"
#             )


#             # ------------------------------------------------
#             # VERIFICAR SE O CHUNK JÁ EXISTE
#             # ------------------------------------------------

#             if chunk_exists(chunk_id):

#                 existing_chunks += 1

#                 continue


#             # ------------------------------------------------
#             # NOVO CHUNK
#             # ------------------------------------------------

#             new_chunks += 1

#             print(
#                 f"Novo chunk: {chunk_id}"
#             )


#             # ------------------------------------------------
#             # GERAR EMBEDDING
#             # ------------------------------------------------

#             embedding = get_openai_embedding(
#                 chunk
#             )


#             # ------------------------------------------------
#             # SALVAR NO POSTGRESQL
#             # ------------------------------------------------

#             conn.execute(
#                 """
#                 INSERT INTO document_qa_collection (
#                     id,
#                     text,
#                     metadata,
#                     embedding
#                 )
#                 VALUES (
#                     %s,
#                     %s,
#                     %s,
#                     %s
#                 )
#                 ON CONFLICT (id)
#                 DO NOTHING;
#                 """,
#                 (
#                     chunk_id,
#                     chunk,
#                     json.dumps(
#                         doc["metadata"]
#                     ),
#                     embedding
#                 )
#             )


#     print(
#         "\n========================================"
#     )

#     print(
#         "RESULTADO DA INDEXAÇÃO"
#     )

#     print(
#         "========================================"
#     )

#     print(
#         f"Total de chunks: {total_chunks}"
#     )

#     print(
#         f"Chunks existentes: {existing_chunks}"
#     )

#     print(
#         f"Novos chunks adicionados: {new_chunks}"
#     )

#     print(
#         "========================================"
#     )


# # ============================================================
# # NÓ 1 DO LANGGRAPH
# #
# # RETRIEVAL
# # ============================================================

# def retrieve_documents(
#     state: GraphState
# ):

#     question = state["question"]


#     print(
#         "\n[LANGGRAPH] retrieve_documents"
#     )


#     # --------------------------------------------------------
#     # GERAR EMBEDDING DA PERGUNTA
#     # --------------------------------------------------------

#     query_embedding = get_openai_embedding(
#         question
#     )


#     # --------------------------------------------------------
#     # BUSCAR DOCUMENTOS SEMELHANTES
#     # --------------------------------------------------------

#     with conn.cursor() as cur:

#         cur.execute(
#             """
#             SELECT
#                 id,
#                 text,
#                 metadata,
#                 1 - (
#                     embedding <=> %s::vector
#                 ) AS similarity
#             FROM document_qa_collection
#             ORDER BY embedding <=> %s::vector
#             LIMIT %s;
#             """,
#             (
#                 query_embedding,
#                 query_embedding,
#                 5
#             )
#         )

#         rows = cur.fetchall()


#     relevant_chunks = []


#     for row in rows:

#         relevant_chunks.append({

#             "id": row[0],

#             "text": row[1],

#             "metadata": row[2],

#             "similarity": row[3]

#         })


#     return {
#         "relevant_chunks": relevant_chunks
#     }


# # ============================================================
# # NÓ 2 DO LANGGRAPH
# #
# # GERAÇÃO DA RESPOSTA
# #
# # AGORA USANDO OPENROUTER
# # ============================================================

# def generate_response(
#     state: GraphState
# ):

#     question = state["question"]

#     relevant_chunks = state[
#         "relevant_chunks"
#     ]


#     print(
#         "\n[LANGGRAPH] generate_response"
#     )


#     # --------------------------------------------------------
#     # CONSTRUIR CONTEXTO
#     # --------------------------------------------------------

#     context_parts = []


#     for i, chunk in enumerate(
#         relevant_chunks,
#         start=1
#     ):

#         metadata = chunk.get(
#             "metadata",
#             {}
#         )


#         titulo = metadata.get(
#             "titulo",
#             ""
#         )


#         data = metadata.get(
#             "data",
#             ""
#         )


#         url = metadata.get(
#             "url",
#             ""
#         )


#         source_info = ""


#         if titulo:

#             source_info += (
#                 f"Título: {titulo}\n"
#             )


#         if data:

#             source_info += (
#                 f"Data: {data}\n"
#             )


#         if url:

#             source_info += (
#                 f"URL: {url}\n"
#             )


#         context_parts.append(
#             f"""
# --- DOCUMENTO {i} ---

# {source_info}

# Conteúdo:
# {chunk["text"]}

# Similaridade:
# {chunk["similarity"]:.4f}
# """
#         )


#     context = "\n".join(
#         context_parts
#     )


#     # ========================================================
#     # PROMPT JORNALÍSTICO
#     # ========================================================

#     prompt = f"""
# Você é um assistente especializado em análise
# e explicação de notícias.

# Seu nome é definido pelo modelo de inteligência artificial que está sendo utilizado atualmente.

# O modelo utilizado nesta conversa é: {LLM_MODEL}
# Ao responder pela primeira vez em uma conversa, se o usuário perguntar quem você é, qual é seu nome, qual modelo você utiliza ou fizer uma pergunta semelhante,
# identifique-se claramente pelo nome do modelo.

# Por exemplo:
#  - Se o modelo for Gemini, diga que você é o Gemini.
#  - Se o modelo for GPT, diga que você é o GPT.
#  - Se o modelo for outro, identifique-se pelo nome correspondente ao modelo utilizado.

# Não diga que você é outro modelo diferente do modelo indicado acima.

# Sua função é responder às perguntas do usuário
# como um jornalista experiente.

# Apresente as informações de maneira:

# - clara;
# - detalhada;
# - objetiva;
# - contextualizada;
# - informativa.

# REGRAS FUNDAMENTAIS:

# 1. Utilize SOMENTE as informações presentes
#    nos documentos fornecidos.

# 2. NÃO invente fatos.

# 3. NÃO invente nomes.

# 4. NÃO invente datas.

# 5. NÃO invente números.

# 6. NÃO invente acontecimentos.

# 7. Não considere uma afirmação verdadeira
#    simplesmente porque ela aparece na pergunta.

# 8. Se os documentos não tiverem informações
#    suficientes para responder à pergunta,
#    informe claramente essa limitação.

# 9. Explique, quando houver informações
#    disponíveis:

#    - o que aconteceu;
#    - quem está envolvido;
#    - onde aconteceu;
#    - quando aconteceu;
#    - como aconteceu;
#    - quais foram as consequências;
#    - qual é o contexto.

# 10. Quando houver informações conflitantes
#     entre os documentos, apresente a divergência.

# 11. Diferencie fatos relatados nos documentos
#     de interpretações.

# 12. Seja detalhado quando houver informações
#     suficientes para isso.

# 13. Não seja excessivamente breve.

# 14. Não invente informações para preencher
#     lacunas.

# 15. Não mencione que você é uma inteligência
#     artificial.

# 16. Não diga que realizou uma busca na internet.

# 17. Baseie a resposta exclusivamente no contexto.

# 18. Sempre mostre a fonte informando a url no final das respostas.

# 19. Sempre informe a data da noticias no inicio das respostas.

# CONTEXTO DOS DOCUMENTOS:

# {context}

# PERGUNTA DO USUÁRIO:

# {question}

# Responda como um jornalista apresentando
# uma informação ao público, fornecendo todos
# os detalhes relevantes que possam ser
# sustentados pelos documentos.
# """


#     # ========================================================
#     # CHAMADA DO OPENROUTER
#     # ========================================================

#     response = llm_client.chat.completions.create(

#         model=LLM_MODEL,

#         messages=[

#             {
#                 "role": "system",
#                 "content": prompt
#             },

#             {
#                 "role": "user",
#                 "content": question
#             }

#         ]

#     )


#     answer = (
#         response
#         .choices[0]
#         .message
#         .content
#     )


#     return {
#         "answer": answer
#     }


# # ============================================================
# # CONSTRUIR GRAFO LANGGRAPH
# # ============================================================

# workflow = StateGraph(
#     GraphState
# )


# # ============================================================
# # ADICIONAR NÓS
# # ============================================================

# workflow.add_node(
#     "retrieve_documents",
#     retrieve_documents
# )

# workflow.add_node(
#     "generate_response",
#     generate_response
# )


# # ============================================================
# # DEFINIR FLUXO
# # ============================================================

# workflow.add_edge(
#     START,
#     "retrieve_documents"
# )

# workflow.add_edge(
#     "retrieve_documents",
#     "generate_response"
# )

# workflow.add_edge(
#     "generate_response",
#     END
# )


# # ============================================================
# # COMPILAR GRAFO
# # ============================================================

# graph = workflow.compile()


# # ============================================================
# # INDEXAÇÃO
# # ============================================================

# json_path = "./news_articles.json"


# documents = load_documents_from_json(
#     json_path
# )


# print(
#     f"\n{len(documents)} documentos encontrados."
# )


# index_documents(
#     documents
# )


# # ============================================================
# # INTERFACE DE PERGUNTAS
# # ============================================================

# print(
#     "\n========================================"
# )

# print(
#     "RAG G1 - LANGGRAPH + PGVECTOR + OPENROUTER"
# )

# print(
#     "========================================"
# )

# print(
#     f"Modelo LLM: {LLM_MODEL}"
# )

# print(
#     "Digite sua pergunta."
# )

# print(
#     "Digite 'exit' para encerrar."
# )

# print(
#     "========================================"
# )


# # ============================================================
# # LOOP DE PERGUNTAS
# # ============================================================

# while True:

#     print()

#     question = input(
#         "Pergunta: "
#     ).strip()


#     # --------------------------------------------------------
#     # SAIR
#     # --------------------------------------------------------

#     if question.lower() == "exit":

#         print(
#             "\nEncerrando o programa..."
#         )

#         break


#     # --------------------------------------------------------
#     # PERGUNTA VAZIA
#     # --------------------------------------------------------

#     if not question:

#         print(
#             "Digite uma pergunta."
#         )

#         continue


#     # ========================================================
#     # EXECUTAR GRAFO
#     # ========================================================

#     result = graph.invoke(
#         {
#             "question": question,

#             "relevant_chunks": [],

#             "answer": ""
#         }
#     )


#     # ========================================================
#     # DOCUMENTOS RECUPERADOS
#     # ========================================================

#     relevant_chunks = result[
#         "relevant_chunks"
#     ]


#     print(
#         "\n=============================="
#     )

#     print(
#         "DOCUMENTOS RECUPERADOS"
#     )

#     print(
#         "=============================="
#     )


#     for i, chunk in enumerate(
#         relevant_chunks,
#         start=1
#     ):

#         metadata = chunk.get(
#             "metadata",
#             {}
#         )


#         titulo = metadata.get(
#             "titulo",
#             ""
#         )


#         print(
#             f"\nDocumento {i}"
#         )


#         if titulo:

#             print(
#                 f"Título: {titulo}"
#             )


#         print(
#             f"Similaridade: "
#             f"{chunk['similarity']:.4f}"
#         )


#     # ========================================================
#     # RESPOSTA
#     # ========================================================

#     print(
#         "\n=============================="
#     )

#     print(
#         "RESPOSTA"
#     )

#     print(
#         "=============================="
#     )


#     print(
#         result["answer"]
#     )


#     print(
#         "=============================="
#     )


# # ============================================================
# # FECHAR CONEXÃO
# # ============================================================

# conn.close()


# print(
#     "Conexão com PostgreSQL encerrada."
# )


























































# import os
# import json

# from dotenv import load_dotenv
# import psycopg
# from pgvector.psycopg import register_vector
# from openai import OpenAI

# from langgraph.graph import StateGraph, START, END
# from typing import TypedDict, List, Dict, Any


# # ============================================================
# # CONFIGURAÇÕES
# # ============================================================

# load_dotenv()


# # ============================================================
# # CHAVE DA OPENAI
# # USADA SOMENTE PARA EMBEDDINGS
# # ============================================================

# openai_key = os.getenv("OPENAI_API_KEY")

# if not openai_key:
#     raise ValueError(
#         "OPENAI_API_KEY não foi encontrada no arquivo .env"
#     )


# # ============================================================
# # CLIENTE OPENAI
# # USADO PARA GERAR OS EMBEDDINGS
# # ============================================================

# openai_client = OpenAI(
#     api_key=openai_key
# )


# # ============================================================
# # CHAVE DO OPENROUTER
# # USADA PARA A LLM
# # ============================================================

# openrouter_key = os.getenv("OPENROUTER_API_KEY")

# if not openrouter_key:
#     raise ValueError(
#         "OPENROUTER_API_KEY não foi encontrada no arquivo .env"
#     )


# # ============================================================
# # CLIENTE OPENROUTER
# # ============================================================

# llm_client = OpenAI(
#     api_key=openrouter_key,
#     base_url="https://openrouter.ai/api/v1"
# )


# # ============================================================
# # MODELO DA LLM
# # ============================================================

# LLM_MODEL = "google/gemini-2.5-flash"


# # ============================================================
# # MODELO DE EMBEDDING
# # ============================================================

# EMBEDDING_MODEL = "text-embedding-3-small"

# EMBEDDING_DIMENSION = 1536


# # ============================================================
# # CONEXÃO COM POSTGRESQL
# # ============================================================

# DB_URI = os.getenv("DB_URI")

# if not DB_URI:
#     raise ValueError(
#         "DB_URI não foi encontrada no arquivo .env"
#     )


# print(
#     "\n==== Conectando ao PostgreSQL ===="
# )


# conn = psycopg.connect(
#     DB_URI,
#     autocommit=True
# )


# print(
#     "PostgreSQL conectado com sucesso!"
# )


# # ============================================================
# # CONFIGURAR PGVECTOR
# # ============================================================

# conn.execute(
#     "CREATE EXTENSION IF NOT EXISTS vector;"
# )


# register_vector(conn)


# print(
#     "pgvector configurado com sucesso!"
# )


# # ============================================================
# # CRIAR TABELA
# #
# # AGORA:
# #
# # UMA LINHA = UMA NOTÍCIA
# #
# # text       = notícia completa
# # metadata   = informações da notícia
# # embedding  = vetor da notícia completa
# # ============================================================

# conn.execute("""
# CREATE TABLE IF NOT EXISTS document_qa_collection (
#     id VARCHAR(255) PRIMARY KEY,
#     text TEXT NOT NULL,
#     metadata JSONB,
#     embedding vector(1536) NOT NULL
# );
# """)


# print(
#     "Tabela document_qa_collection pronta!"
# )


# # ============================================================
# # CRIAR ÍNDICE VETORIAL
# # ============================================================

# conn.execute("""
# CREATE INDEX IF NOT EXISTS
# document_qa_collection_embedding_idx
# ON document_qa_collection
# USING hnsw (embedding vector_cosine_ops);
# """)


# print(
#     "Índice HNSW do pgvector configurado!"
# )


# # ============================================================
# # ESTADO DO LANGGRAPH
# # ============================================================

# class GraphState(TypedDict):

#     question: str

#     relevant_chunks: List[Dict[str, Any]]

#     answer: str


# # ============================================================
# # CARREGAR DOCUMENTOS DO JSON
# # ============================================================

# def load_documents_from_json(json_path):

#     print(
#         "\n==== Verificando arquivo JSON ===="
#     )


#     with open(
#         json_path,
#         "r",
#         encoding="utf-8"
#     ) as file:

#         data = json.load(file)


#     documents = []


#     for article in data:

#         metadata = article.get(
#             "metadata",
#             {}
#         )


#         titulo = metadata.get(
#             "titulo",
#             ""
#         )


#         texto = article.get(
#             "texto",
#             ""
#         )


#         # ----------------------------------------------------
#         # A NOTÍCIA COMPLETA
#         #
#         # O embedding será gerado deste conteúdo inteiro.
#         # ----------------------------------------------------

#         conteudo = (
#             f"{titulo}\n\n{texto}"
#         )


#         documents.append({

#             "id": article["id"],

#             "text": conteudo,

#             "metadata": metadata

#         })


#     return documents


# # ============================================================
# # GERAR EMBEDDING DA NOTÍCIA
# # ============================================================

# def get_openai_embedding(text):

#     response = openai_client.embeddings.create(

#         input=text,

#         model=EMBEDDING_MODEL

#     )


#     return response.data[0].embedding


# # ============================================================
# # VERIFICAR SE A NOTÍCIA JÁ EXISTE
# # ============================================================

# def article_exists(article_id):

#     with conn.cursor() as cur:

#         cur.execute(
#             """
#             SELECT 1
#             FROM document_qa_collection
#             WHERE id = %s
#             LIMIT 1;
#             """,
#             (article_id,)
#         )


#         return cur.fetchone() is not None


# # ============================================================
# # INDEXAR NOTÍCIAS
# #
# # AGORA:
# #
# # UMA NOTÍCIA = UMA LINHA
# #
# # Não existe mais chunk.
# # ============================================================

# def index_documents(documents):

#     print(
#         "\n==== Verificando notícias existentes ===="
#     )


#     total_news = 0

#     new_news = 0

#     existing_news = 0


#     for doc in documents:

#         total_news += 1


#         article_id = doc["id"]


#         # ----------------------------------------------------
#         # VERIFICAR SE A NOTÍCIA JÁ EXISTE
#         # ----------------------------------------------------

#         if article_exists(article_id):

#             existing_news += 1

#             print(
#                 f"Notícia já existente: {article_id}"
#             )

#             continue


#         # ----------------------------------------------------
#         # NOVA NOTÍCIA
#         # ----------------------------------------------------

#         new_news += 1


#         print(
#             f"\nNova notícia: {article_id}"
#         )


#         metadata = doc["metadata"]


#         titulo = metadata.get(
#             "titulo",
#             ""
#         )


#         if titulo:

#             print(
#                 f"Título: {titulo}"
#             )


#         # ----------------------------------------------------
#         # GERAR EMBEDDING DA NOTÍCIA INTEIRA
#         # ----------------------------------------------------

#         print(
#             "Gerando embedding..."
#         )


#         embedding = get_openai_embedding(
#             doc["text"]
#         )


#         # ----------------------------------------------------
#         # SALVAR NOTÍCIA NO POSTGRESQL
#         # ----------------------------------------------------

#         conn.execute(
#             """
#             INSERT INTO document_qa_collection (
#                 id,
#                 text,
#                 metadata,
#                 embedding
#             )
#             VALUES (
#                 %s,
#                 %s,
#                 %s,
#                 %s
#             )
#             ON CONFLICT (id)
#             DO NOTHING;
#             """,
#             (
#                 article_id,

#                 doc["text"],

#                 json.dumps(
#                     metadata,
#                     ensure_ascii=False
#                 ),

#                 embedding
#             )
#         )


#         print(
#             "Notícia inserida no PostgreSQL."
#         )


#     print(
#         "\n========================================"
#     )

#     print(
#         "RESULTADO DA INDEXAÇÃO"
#     )

#     print(
#         "========================================"
#     )

#     print(
#         f"Total de notícias: {total_news}"
#     )

#     print(
#         f"Notícias existentes: {existing_news}"
#     )

#     print(
#         f"Novas notícias adicionadas: {new_news}"
#     )

#     print(
#         "========================================"
#     )


# # ============================================================
# # NÓ 1 DO LANGGRAPH
# #
# # RETRIEVAL
# # ============================================================

# def retrieve_documents(
#     state: GraphState
# ):

#     question = state["question"]


#     print(
#         "\n[LANGGRAPH] retrieve_documents"
#     )


#     # --------------------------------------------------------
#     # GERAR EMBEDDING DA PERGUNTA
#     # --------------------------------------------------------

#     query_embedding = get_openai_embedding(
#         question
#     )


#     # --------------------------------------------------------
#     # BUSCAR NOTÍCIAS SEMELHANTES
#     #
#     # Agora cada resultado corresponde a UMA NOTÍCIA.
#     # --------------------------------------------------------

#     with conn.cursor() as cur:

#         cur.execute(
#             """
#             SELECT
#                 id,
#                 text,
#                 metadata,
#                 1 - (
#                     embedding <=> %s::vector
#                 ) AS similarity
#             FROM document_qa_collection
#             ORDER BY embedding <=> %s::vector
#             LIMIT %s;
#             """,
#             (
#                 query_embedding,

#                 query_embedding,

#                 5
#             )
#         )


#         rows = cur.fetchall()


#     relevant_chunks = []


#     for row in rows:

#         relevant_chunks.append({

#             "id": row[0],

#             "text": row[1],

#             "metadata": row[2],

#             "similarity": row[3]

#         })


#     return {
#         "relevant_chunks": relevant_chunks
#     }


# # ============================================================
# # NÓ 2 DO LANGGRAPH
# #
# # GERAÇÃO DA RESPOSTA
# # ============================================================

# def generate_response(
#     state: GraphState
# ):

#     question = state["question"]


#     relevant_chunks = state[
#         "relevant_chunks"
#     ]


#     print(
#         "\n[LANGGRAPH] generate_response"
#     )


#     # --------------------------------------------------------
#     # CONSTRUIR CONTEXTO
#     # --------------------------------------------------------

#     context_parts = []


#     for i, article in enumerate(
#         relevant_chunks,
#         start=1
#     ):

#         metadata = article.get(
#             "metadata",
#             {}
#         )


#         titulo = metadata.get(
#             "titulo",
#             ""
#         )


#         data = metadata.get(
#             "data",
#             ""
#         )


#         url = metadata.get(
#             "url",
#             ""
#         )


#         source_info = ""


#         if titulo:

#             source_info += (
#                 f"Título: {titulo}\n"
#             )


#         if data:

#             source_info += (
#                 f"Data: {data}\n"
#             )


#         if url:

#             source_info += (
#                 f"URL: {url}\n"
#             )


#         context_parts.append(
#             f"""
# --- NOTÍCIA {i} ---

# {source_info}

# Conteúdo:
# {article["text"]}

# Similaridade:
# {article["similarity"]:.4f}
# """
#         )


#     context = "\n".join(
#         context_parts
#     )


#     # ========================================================
#     # PROMPT JORNALÍSTICO
#     # ========================================================

#     prompt = f"""
# Você é um assistente especializado em análise
# e explicação de notícias.

# Seu nome é definido pelo modelo de inteligência artificial que está sendo utilizado atualmente.

# O modelo utilizado nesta conversa é: {LLM_MODEL}

# Ao responder pela primeira vez em uma conversa,
# se o usuário perguntar quem você é, qual é seu nome,
# qual modelo você utiliza ou fizer uma pergunta semelhante,
# identifique-se claramente pelo nome do modelo.

# Por exemplo:

# - Se o modelo for Gemini, diga que você é o Gemini.
# - Se o modelo for GPT, diga que você é o GPT.
# - Se o modelo for outro, identifique-se pelo nome
#   correspondente ao modelo utilizado.

# Não diga que você é outro modelo diferente
# do modelo indicado acima.


# Sua função é responder às perguntas do usuário
# como um jornalista experiente.


# Apresente as informações de maneira:

# - clara;
# - detalhada;
# - objetiva;
# - contextualizada;
# - informativa.


# REGRAS FUNDAMENTAIS:


# 1. Utilize SOMENTE as informações presentes
#    nas notícias fornecidas.


# 2. NÃO invente fatos.


# 3. NÃO invente nomes.


# 4. NÃO invente datas.


# 5. NÃO invente números.


# 6. NÃO invente acontecimentos.


# 7. Não considere uma afirmação verdadeira
#    simplesmente porque ela aparece na pergunta.


# 8. Se as notícias não tiverem informações
#    suficientes para responder à pergunta,
#    informe claramente essa limitação.


# 9. Explique, quando houver informações
#    disponíveis:

#    - o que aconteceu;
#    - quem está envolvido;
#    - onde aconteceu;
#    - quando aconteceu;
#    - como aconteceu;
#    - quais foram as consequências;
#    - qual é o contexto.


# 10. Quando houver informações conflitantes
#     entre as notícias, apresente a divergência.


# 11. Diferencie fatos relatados nas notícias
#     de interpretações.


# 12. Seja detalhado quando houver informações
#     suficientes para isso.


# 13. Não seja excessivamente breve.


# 14. Não invente informações para preencher
#     lacunas.


# 15. Não mencione que você é uma inteligência
#     artificial.


# 16. Não diga que realizou uma busca na internet.


# 17. Baseie a resposta exclusivamente
#     no contexto fornecido.


# 18. Sempre mostre a fonte informando
#     a URL no final das respostas.


# 19. Sempre informe a data da notícia
#     no início das respostas.


# CONTEXTO DAS NOTÍCIAS:

# {context}


# PERGUNTA DO USUÁRIO:

# {question}


# Responda como um jornalista apresentando
# uma informação ao público, fornecendo todos
# os detalhes relevantes que possam ser
# sustentados pelas notícias fornecidas.
# """


#     # ========================================================
#     # CHAMADA DO OPENROUTER
#     # ========================================================

#     response = llm_client.chat.completions.create(

#         model=LLM_MODEL,

#         messages=[

#             {
#                 "role": "system",
#                 "content": prompt
#             },

#             {
#                 "role": "user",
#                 "content": question
#             }

#         ]

#     )


#     answer = (
#         response
#         .choices[0]
#         .message
#         .content
#     )


#     return {
#         "answer": answer
#     }


# # ============================================================
# # CONSTRUIR GRAFO LANGGRAPH
# # ============================================================

# workflow = StateGraph(
#     GraphState
# )


# # ============================================================
# # ADICIONAR NÓS
# # ============================================================

# workflow.add_node(
#     "retrieve_documents",
#     retrieve_documents
# )


# workflow.add_node(
#     "generate_response",
#     generate_response
# )


# # ============================================================
# # DEFINIR FLUXO
# # ============================================================

# workflow.add_edge(
#     START,
#     "retrieve_documents"
# )


# workflow.add_edge(
#     "retrieve_documents",
#     "generate_response"
# )


# workflow.add_edge(
#     "generate_response",
#     END
# )


# # ============================================================
# # COMPILAR GRAFO
# # ============================================================

# graph = workflow.compile()


# # ============================================================
# # INDEXAÇÃO
# # ============================================================

# json_path = "./news_articles.json"


# documents = load_documents_from_json(
#     json_path
# )


# print(
#     f"\n{len(documents)} notícias encontradas."
# )


# index_documents(
#     documents
# )


# # ============================================================
# # INTERFACE DE PERGUNTAS
# # ============================================================

# print(
#     "\n========================================"
# )


# print(
#     "RAG G1 - LANGGRAPH + PGVECTOR + OPENROUTER"
# )


# print(
#     "========================================"
# )


# print(
#     f"Modelo LLM: {LLM_MODEL}"
# )


# print(
#     f"Modelo Embedding: {EMBEDDING_MODEL}"
# )


# print(
#     "Estrutura: 1 linha = 1 notícia"
# )


# print(
#     "Digite sua pergunta."
# )


# print(
#     "Digite 'exit' para encerrar."
# )


# print(
#     "========================================"
# )


# # ============================================================
# # LOOP DE PERGUNTAS
# # ============================================================

# while True:

#     print()


#     question = input(
#         "Pergunta: "
#     ).strip()


#     # --------------------------------------------------------
#     # SAIR
#     # --------------------------------------------------------

#     if question.lower() == "exit":

#         print(
#             "\nEncerrando o programa..."
#         )

#         break


#     # --------------------------------------------------------
#     # PERGUNTA VAZIA
#     # --------------------------------------------------------

#     if not question:

#         print(
#             "Digite uma pergunta."
#         )

#         continue


#     # ========================================================
#     # EXECUTAR GRAFO
#     # ========================================================

#     result = graph.invoke(
#         {
#             "question": question,

#             "relevant_chunks": [],

#             "answer": ""
#         }
#     )


#     # ========================================================
#     # NOTÍCIAS RECUPERADAS
#     # ========================================================

#     relevant_chunks = result[
#         "relevant_chunks"
#     ]


#     print(
#         "\n=============================="
#     )


#     print(
#         "NOTÍCIAS RECUPERADAS"
#     )


#     print(
#         "=============================="
#     )


#     for i, article in enumerate(
#         relevant_chunks,
#         start=1
#     ):

#         metadata = article.get(
#             "metadata",
#             {}
#         )


#         titulo = metadata.get(
#             "titulo",
#             ""
#         )


#         data = metadata.get(
#             "data",
#             ""
#         )


#         print(
#             f"\nNotícia {i}"
#         )


#         if titulo:

#             print(
#                 f"Título: {titulo}"
#             )


#         if data:

#             print(
#                 f"Data: {data}"
#             )


#         print(
#             f"Similaridade: "
#             f"{article['similarity']:.4f}"
#         )


#     # ========================================================
#     # RESPOSTA
#     # ========================================================

#     print(
#         "\n=============================="
#     )


#     print(
#         "RESPOSTA"
#     )


#     print(
#         "=============================="
#     )


#     print(
#         result["answer"]
#     )


#     print(
#         "=============================="
#     )


# # ============================================================
# # FECHAR CONEXÃO
# # ============================================================

# conn.close()


# print(
#     "Conexão com PostgreSQL encerrada."
# )
























































import os
import json

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector
from openai import OpenAI

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Dict, Any


# ============================================================
# CONFIGURAÇÕES
# ============================================================

load_dotenv()


# ============================================================
# CHAVE DA OPENAI
# USADA SOMENTE PARA EMBEDDINGS
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
# CHAVE DO OPENROUTER
# USADA PARA A LLM
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

EMBEDDING_DIMENSION = 1536


# ============================================================
# CONFIGURAÇÕES DOS CHUNKS
# ============================================================

CHUNK_SIZE = 1000

CHUNK_OVERLAP = 200


# ============================================================
# QUANTIDADE DE CHUNKS RECUPERADOS
# ============================================================

TOP_K = 5


# ============================================================
# CONEXÃO COM POSTGRESQL
# ============================================================

DB_URI = os.getenv("DB_URI")

if not DB_URI:
    raise ValueError(
        "DB_URI não foi encontrada no arquivo .env"
    )


print(
    "\n==== Conectando ao PostgreSQL ===="
)


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
# TABELA DE NOTÍCIAS
#
# UMA LINHA = UMA NOTÍCIA
#
# A notícia original fica armazenada aqui.
#
# IMPORTANTE:
# A notícia inteira NÃO possui embedding.
# ============================================================

conn.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id VARCHAR(255) PRIMARY KEY,
    text TEXT NOT NULL,
    metadata JSONB
);
""")


print(
    "Tabela articles pronta!"
)


# ============================================================
# TABELA DE CHUNKS
#
# UMA LINHA = UM CHUNK
#
# Cada chunk possui:
#
# - sua própria identificação
# - identificação da notícia
# - posição dentro da notícia
# - texto
# - embedding
# ============================================================

conn.execute("""
CREATE TABLE IF NOT EXISTS article_chunks (
    id VARCHAR(255) PRIMARY KEY,

    article_id VARCHAR(255) NOT NULL,

    chunk_index INTEGER NOT NULL,

    text TEXT NOT NULL,

    embedding vector(1536) NOT NULL,

    CONSTRAINT fk_article
        FOREIGN KEY (article_id)
        REFERENCES articles(id)
        ON DELETE CASCADE,

    CONSTRAINT unique_article_chunk
        UNIQUE (article_id, chunk_index)
);
""")


print(
    "Tabela article_chunks pronta!"
)


# ============================================================
# ÍNDICE HNSW
#
# Usado para acelerar a busca vetorial.
# ============================================================

conn.execute("""
CREATE INDEX IF NOT EXISTS
article_chunks_embedding_idx
ON article_chunks
USING hnsw (embedding vector_cosine_ops);
""")


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
# CARREGAR DOCUMENTOS DO JSON
# ============================================================

def load_documents_from_json(json_path):

    print(
        "\n==== Verificando arquivo JSON ===="
    )


    with open(
        json_path,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)


    documents = []


    for article in data:

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


        # ----------------------------------------------------
        # TEXTO COMPLETO DA NOTÍCIA
        # ----------------------------------------------------

        conteudo = (
            f"{titulo}\n\n{texto}"
        )


        documents.append({

            "id": article["id"],

            "text": conteudo,

            "metadata": metadata

        })


    return documents


# ============================================================
# DIVIDIR NOTÍCIA EM CHUNKS
# ============================================================

def split_text(
    text,
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
):

    chunks = []


    start = 0


    while start < len(text):

        end = start + chunk_size


        chunk = text[start:end].strip()


        if chunk:

            chunks.append(
                chunk
            )


        if end >= len(text):

            break


        start = end - chunk_overlap


    return chunks


# ============================================================
# GERAR EMBEDDING
# ============================================================

def get_openai_embedding(text):

    response = openai_client.embeddings.create(

        input=text,

        model=EMBEDDING_MODEL

    )


    return response.data[0].embedding


# ============================================================
# VERIFICAR SE A NOTÍCIA JÁ EXISTE
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
# VERIFICAR SE O CHUNK JÁ EXISTE
# ============================================================

def chunk_exists(
    article_id,
    chunk_index
):

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT 1
            FROM article_chunks
            WHERE article_id = %s
              AND chunk_index = %s
            LIMIT 1;
            """,
            (
                article_id,
                chunk_index
            )
        )


        return cur.fetchone() is not None


# ============================================================
# INDEXAR DOCUMENTOS
#
# FLUXO:
#
# 1. Salva a notícia original
# 2. Divide a notícia em chunks
# 3. Gera embedding de cada chunk
# 4. Salva os chunks
#
# A notícia inteira NÃO é vetorizada.
# ============================================================

def index_documents(documents):

    print(
        "\n==== Iniciando indexação ===="
    )


    total_articles = 0

    new_articles = 0

    existing_articles = 0

    total_chunks = 0

    new_chunks = 0

    existing_chunks = 0


    for doc in documents:

        total_articles += 1


        article_id = doc["id"]


        # ====================================================
        # VERIFICAR NOTÍCIA
        # ====================================================

        if article_exists(article_id):

            existing_articles += 1


            print(
                f"\nNotícia já existe: {article_id}"
            )

        else:

            new_articles += 1


            print(
                f"\nNova notícia: {article_id}"
            )


            # ------------------------------------------------
            # SALVAR NOTÍCIA ORIGINAL
            # ------------------------------------------------

            conn.execute(
                """
                INSERT INTO articles (
                    id,
                    text,
                    metadata
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (id)
                DO NOTHING;
                """,
                (
                    article_id,

                    doc["text"],

                    json.dumps(
                        doc["metadata"],
                        ensure_ascii=False
                    )
                )
            )


            print(
                "Notícia original salva."
            )


        # ====================================================
        # DIVIDIR NOTÍCIA
        # ====================================================

        chunks = split_text(
            doc["text"]
        )


        print(
            f"Quantidade de chunks: "
            f"{len(chunks)}"
        )


        # ====================================================
        # PROCESSAR CHUNKS
        # ====================================================

        for i, chunk in enumerate(chunks):

            total_chunks += 1


            # ------------------------------------------------
            # ID DO CHUNK
            # ------------------------------------------------

            chunk_id = (
                f"{article_id}_chunk_{i}"
            )


            # ------------------------------------------------
            # VERIFICAR SE JÁ EXISTE
            # ------------------------------------------------

            if chunk_exists(
                article_id,
                i
            ):

                existing_chunks += 1


                continue


            # ------------------------------------------------
            # NOVO CHUNK
            # ------------------------------------------------

            new_chunks += 1


            print(
                f"Gerando embedding: "
                f"{chunk_id}"
            )


            # ------------------------------------------------
            # EMBEDDING DO CHUNK
            # ------------------------------------------------

            embedding = get_openai_embedding(
                chunk
            )


            # ------------------------------------------------
            # SALVAR CHUNK
            # ------------------------------------------------

            conn.execute(
                """
                INSERT INTO article_chunks (
                    id,
                    article_id,
                    chunk_index,
                    text,
                    embedding
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (id)
                DO NOTHING;
                """,
                (
                    chunk_id,

                    article_id,

                    i,

                    chunk,

                    embedding
                )
            )


    # ========================================================
    # RESULTADO
    # ========================================================

    print(
        "\n========================================"
    )


    print(
        "RESULTADO DA INDEXAÇÃO"
    )


    print(
        "========================================"
    )


    print(
        f"Total de notícias: "
        f"{total_articles}"
    )


    print(
        f"Notícias existentes: "
        f"{existing_articles}"
    )


    print(
        f"Novas notícias: "
        f"{new_articles}"
    )


    print(
        f"Total de chunks: "
        f"{total_chunks}"
    )


    print(
        f"Chunks existentes: "
        f"{existing_chunks}"
    )


    print(
        f"Novos chunks: "
        f"{new_chunks}"
    )


    print(
        "========================================"
    )


# ============================================================
# NÓ 1 DO LANGGRAPH
#
# RETRIEVAL
# ============================================================

def retrieve_documents(
    state: GraphState
):

    question = state["question"]


    print(
        "\n[LANGGRAPH] retrieve_documents"
    )


    # ========================================================
    # EMBEDDING DA PERGUNTA
    # ========================================================

    query_embedding = get_openai_embedding(
        question
    )


    # ========================================================
    # BUSCAR CHUNKS MAIS SEMELHANTES
    #
    # IMPORTANTE:
    #
    # A busca é feita diretamente nos embeddings
    # armazenados na tabela article_chunks.
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
                ) AS similarity,

                a.metadata

            FROM article_chunks ac

            INNER JOIN articles a
                ON a.id = ac.article_id

            ORDER BY
                ac.embedding <=> %s::vector

            LIMIT %s;
            """,
            (
                query_embedding,

                query_embedding,

                query_embedding,

                TOP_K
            )
        )


        rows = cur.fetchall()


    # ========================================================
    # ORGANIZAR RESULTADOS
    # ========================================================

    relevant_chunks = []


    for row in rows:

        relevant_chunks.append({

            "id": row[0],

            "article_id": row[1],

            "chunk_index": row[2],

            "text": row[3],

            "distance": row[4],

            "similarity": row[5],

            "metadata": row[6]

        })


    return {
        "relevant_chunks": relevant_chunks
    }


# ============================================================
# NÓ 2 DO LANGGRAPH
#
# GERAÇÃO DA RESPOSTA
# ============================================================

def generate_response(
    state: GraphState
):

    question = state["question"]


    relevant_chunks = state[
        "relevant_chunks"
    ]


    print(
        "\n[LANGGRAPH] generate_response"
    )


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


        titulo = metadata.get(
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

Notícia:
{chunk["article_id"]}

Posição do trecho:
{chunk["chunk_index"]}

Conteúdo:
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

Seu nome é definido pelo modelo de inteligência
artificial que está sendo utilizado atualmente.

O modelo utilizado nesta conversa é: {LLM_MODEL}

Ao responder pela primeira vez em uma conversa,
se o usuário perguntar quem você é, qual é seu nome,
qual modelo você utiliza ou fizer uma pergunta semelhante,
identifique-se claramente pelo nome do modelo.

Não diga que você é outro modelo diferente
do modelo indicado acima.


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
   nos documentos fornecidos.


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


9. Explique, quando houver informações
   disponíveis:

   - o que aconteceu;
   - quem está envolvido;
   - onde aconteceu;
   - quando aconteceu;
   - como aconteceu;
   - quais foram as consequências;
   - qual é o contexto.


10. Quando houver informações conflitantes
    entre os documentos, apresente a divergência.


11. Diferencie fatos relatados nos documentos
    de interpretações.


12. Seja detalhado quando houver informações
    suficientes para isso.


13. Não seja excessivamente breve.


14. Não invente informações para preencher
    lacunas.


15. Não mencione que você é uma inteligência
    artificial.


16. Não diga que realizou uma busca na internet.


17. Baseie a resposta exclusivamente
    no contexto fornecido.


18. Sempre mostre a fonte informando
    a URL no final da resposta.


19. Sempre informe a data da notícia
    no início da resposta.


20. Os documentos apresentados são trechos
    de notícias.

    Os trechos pertencentes à mesma notícia
    possuem o mesmo identificador de notícia.


21. Se os trechos disponíveis não forem
    suficientes para responder à pergunta,
    informe claramente essa limitação.


CONTEXTO:

{context}


PERGUNTA DO USUÁRIO:

{question}


Responda como um jornalista apresentando
uma informação ao público, fornecendo todos
os detalhes relevantes que possam ser
sustentados pelos documentos fornecidos.
"""


    # ========================================================
    # OPENROUTER
    # ========================================================

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


# ============================================================
# NÓS
# ============================================================

workflow.add_node(
    "retrieve_documents",
    retrieve_documents
)


workflow.add_node(
    "generate_response",
    generate_response
)


# ============================================================
# FLUXO
# ============================================================

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


# ============================================================
# COMPILAR
# ============================================================

graph = workflow.compile()


# ============================================================
# INDEXAÇÃO
# ============================================================

json_path = "./news_articles.json"


documents = load_documents_from_json(
    json_path
)


print(
    f"\n{len(documents)} notícias encontradas."
)


index_documents(
    documents
)


# ============================================================
# INTERFACE
# ============================================================

print(
    "\n========================================"
)


print(
    "RAG G1 - LANGGRAPH + PGVECTOR + OPENROUTER"
)


print(
    "========================================"
)


print(
    f"Modelo LLM: {LLM_MODEL}"
)


print(
    f"Modelo Embedding: {EMBEDDING_MODEL}"
)


print(
    "Arquitetura:"
)


print(
    "1 linha = 1 notícia"
)


print(
    "Chunks = tabela separada"
)


print(
    "Embedding = somente dos chunks"
)


print(
    "Digite sua pergunta."
)


print(
    "Digite 'exit' para encerrar."
)


print(
    "========================================"
)


# ============================================================
# LOOP DE PERGUNTAS
# ============================================================

while True:

    print()


    question = input(
        "Pergunta: "
    ).strip()


    # --------------------------------------------------------
    # SAIR
    # --------------------------------------------------------

    if question.lower() == "exit":

        print(
            "\nEncerrando o programa..."
        )

        break


    # --------------------------------------------------------
    # PERGUNTA VAZIA
    # --------------------------------------------------------

    if not question:

        print(
            "Digite uma pergunta."
        )

        continue


    # ========================================================
    # EXECUTAR LANGGRAPH
    # ========================================================

    result = graph.invoke(
        {
            "question": question,

            "relevant_chunks": [],

            "answer": ""
        }
    )


    # ========================================================
    # DOCUMENTOS RECUPERADOS
    # ========================================================

    relevant_chunks = result[
        "relevant_chunks"
    ]


    print(
        "\n=============================="
    )


    print(
        "CHUNKS RECUPERADOS"
    )


    print(
        "=============================="
    )


    for i, chunk in enumerate(
        relevant_chunks,
        start=1
    ):

        metadata = chunk.get(
            "metadata",
            {}
        )


        titulo = metadata.get(
            "titulo",
            ""
        )


        print(
            f"\nChunk {i}"
        )


        print(
            f"Notícia: "
            f"{chunk['article_id']}"
        )


        print(
            f"Chunk index: "
            f"{chunk['chunk_index']}"
        )


        if titulo:

            print(
                f"Título: {titulo}"
            )


        print(
            f"Similaridade: "
            f"{chunk['similarity']:.4f}"
        )


    # ========================================================
    # RESPOSTA
    # ========================================================

    print(
        "\n=============================="
    )


    print(
        "RESPOSTA"
    )


    print(
        "=============================="
    )


    print(
        result["answer"]
    )


    print(
        "=============================="
    )


# ============================================================
# FECHAR CONEXÃO
# ============================================================

conn.close()


print(
    "Conexão com PostgreSQL encerrada."
)

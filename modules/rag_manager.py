import os
from chromadb import ChromaDB
from ollama_api import OllamaAPI
import json

class RAGManager:
    def __init__(self):
        self.chroma_db = None
        self.ollama_api = None

    def add_document(self, filepath):
        try:
            with open(filepath, 'r') as file:
                text = file.read()
                embeddings = self.get_embeddings(text)
                self.chroma_db.add_embedding(embeddings, filepath)
        except FileNotFoundError:
            print("Fichier introuvable")

    def search(self, query, top_k=3):
        try:
            results = self.chroma_db.search(query, top_k=top_k)
            return [result['filepath'] for result in results]
        except Exception as e:
            print(f"Erreur de recherche : {e}")

    def get_context(self, query):
        try:
            documents = self.search(query)
            context = []
            for document in documents:
                text = open(document, 'r').read()
                chunks = [text[i:i+500] for i in range(0, len(text), 500)]
                context.append(chunks)
            return context
        except Exception as e:
            print(f"Erreur de récupération du contexte : {e}")

    def get_embeddings(self, text):
        if self.ollama_api is None:
            self.ollama_api = OllamaAPI()
        embeddings = self.ollama_api.get_embeddings(text)
        return embeddings

    def setup_chroma_db(self):
        try:
            self.chroma_db = ChromaDB()
        except Exception as e:
            print(f"Erreur de configuration de ChromaDB : {e}")

    def fallback_search(self, query):
        documents = os.listdir('data')
        matching_documents = [document for document in documents if query.lower() in document.lower()]
        return matching_documents

    def handle_errors(self, exception):
        if isinstance(exception, FileNotFoundError):
            print("Fichier introuvable")
        elif isinstance(exception, Exception):
            print(f"Erreur inconnue : {exception}")

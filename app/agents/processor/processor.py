import os
import openai
import re
import numpy as np
import openai
from sklearn.feature_extraction.text import TfidfVectorizer
from pinecone import Pinecone, ServerlessSpec
from app.config import OPENAI, PINECONE

class Processor:
    def __init__(self, openai_api_key, pinecone_api_key, pinecone_environment):
        # Initialize OpenAI API key
        openai.api_key = OPENAI
        
        # Initialize Pinecone
        self.pinecone_client = Pinecone(api_key=PINECONE)
        
    def generate_embeddings(self, text):
        """
        Generate embeddings for the given text using OpenAI's embedding model.
        """
        response = openai.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        embedding = response.data[0].embedding
        return np.array(embedding, dtype=np.float32)

    def store_embeddings_in_pinecone(self, index_name, embeddings, metadata):
        """
        Store the embeddings in a Pinecone index.
        """
        # Create or connect to an existing index
        if index_name not in self.pinecone_client.list_indexes().names():
            self.pinecone_client.create_index(
                name=index_name, 
                dimension=embeddings.shape[1], 
                metric='euclidean',
                spec=ServerlessSpec(
                    cloud='aws',
                    region='us-east-1'
                )
            )
        
        index = self.pinecone_client.Index(index_name)
        
        # Upsert embeddings into Pinecone index
        pinecone_vectors = [(str(i), embeddings[i], {"file_path": metadata[i]}) for i in range(len(metadata))]
        index.upsert(vectors=pinecone_vectors)
        return index

    def query_pinecone_with_threshold(self, index, prompt_embedding, similarity_threshold=0.75):
        """
        Query Pinecone to retrieve relevant files based on a similarity threshold.
        """
        # Query the index with the prompt embedding
        query_response = index.query(vector=prompt_embedding.tolist(), top_k=10000, include_metadata=True)
        relevant_files = []
        for match in query_response['matches']:
            similarity = 1 / (1 + match['score'])  # Convert distance to similarity
            if similarity >= similarity_threshold:
                relevant_files.append(match['metadata']['file_path'])
        
        return relevant_files

    def update_embeddings(self, index_name, file_path):
        """
        Update the embedding for a specific file in the Pinecone index if it has changed.
        """
        index = self.pinecone_client.Index(index_name)
        
        # Read the file content and generate new embedding
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            new_embedding = self.generate_embeddings(content)
        
        # Generate an ID based on the file path (or use a more robust method)
        file_id = str(hash(file_path))
        
        # Upsert the updated embedding into Pinecone
        index.upsert(vectors=[(file_id, new_embedding, {"file_path": file_path})])
        print(f"Updated embedding for file: {file_path}")

    def analyze_dependencies(self, file_path):
        """
        Analyze a code file for dependencies by searching for common import/include patterns.
        """
        dependency_patterns = [
            r'#include\s*["<](.*?)[">]',        # C/C++ #include "file.h" or <file.h>
            r'import\s+(\S+)',                  # Python, Java, JavaScript import statement
            r'from\s+(\S+)\s+import',           # Python specific from ... import ...
            r'using\s+namespace\s+(\S+)',       # C++ using namespace
            r'require\(\s*["\'](.*?)["\']\s*\)', # JavaScript/Node.js require('module')
            r'include\s+(\S+)',                 # Ruby include or PHP include
            r'include\s*[\'"](.*?)[\'"]',       # PHP specific include or require
            # Add more patterns as needed for other languages
        ]

        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            imports = set()
            for pattern in dependency_patterns:
                matches = re.findall(pattern, content)
                imports.update(matches)
            
        return imports

    def expand_with_dependencies(self, relevant_files):
        """
        Expand the set of relevant files to include dependencies such as imports/includes.
        """
        expanded_files = set(relevant_files)
        codebase_files = {file for root, _, files in os.walk(".") for file in files}

        for file in relevant_files:
            imports = self.analyze_dependencies(file)
            for imported_module in imports:
                # Search for matching files in the codebase
                for candidate_file in codebase_files:
                    if imported_module in candidate_file:
                        expanded_files.add(candidate_file)
        
        return list(expanded_files)

    def contextual_expansion(self, keywords, codebase_files):
        """
        Perform a contextual expansion to ensure all relevant files are captured based on keywords.
        """
        contextual_files = set()

        for keyword in keywords:
            for file in codebase_files:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if keyword in content:
                        contextual_files.add(file)

        return list(contextual_files)

    def extract_keywords(self, prompt, top_n=5):
        """
        Extract keywords from the user prompt using TF-IDF.
        """
        # Use 'english' stopwords
        vectorizer = TfidfVectorizer(stop_words='english', max_features=top_n)
        
        # Fit the vectorizer on the prompt
        X = vectorizer.fit_transform([prompt])
        
        # Extract the top N keywords
        keywords = vectorizer.get_feature_names_out()
        return keywords

    def process_directory(self, dir_path, user_prompt, index_name="repo-index", similarity_threshold=0.6):
        """
        Main method to process a directory, generate embeddings, and find relevant files.
        """
        embeddings = []
        metadata = []
        
        # Step 1: Extract keywords from the user prompt
        keywords = self.extract_keywords(user_prompt)
        keyword_text = " ".join(keywords)
        
        # Step 2: Generate embeddings for all files in the directory
        codebase_files = []
        for root, dirs, files in os.walk(dir_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    embedding = self.generate_embeddings(content)
                    embeddings.append(embedding)
                    metadata.append(file_path)
                    codebase_files.append(file_path)
        
        embeddings = np.vstack(embeddings)  # Convert list of embeddings to a numpy array
        
        # Step 3: Store embeddings in Pinecone
        index = self.store_embeddings_in_pinecone(index_name, embeddings, metadata)
        
        # Step 4: Generate embedding for user keywords
        keyword_embedding = self.generate_embeddings(keyword_text)
        
        # Step 5: Query Pinecone for relevant files using the similarity threshold
        relevant_files = self.query_pinecone_with_threshold(index, keyword_embedding, similarity_threshold)
        
        # Step 6: Expand relevant files with dependencies
        relevant_files_with_dependencies = self.expand_with_dependencies(relevant_files)
        
        # Step 7: Perform contextual expansion based on keywords
        final_relevant_files = set(relevant_files_with_dependencies).union(
            set(self.contextual_expansion(keywords, codebase_files))
        )
        
        return list(final_relevant_files)


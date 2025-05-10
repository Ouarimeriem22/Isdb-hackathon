import json
import os
from sentence_transformers import SentenceTransformer, util
import numpy as np
from openai import OpenAI
from .utils import chunk_text, preprocess_text # Assumes utils.py is in the same 'modules' directory

MODEL_NAME = 'all-MiniLM-L6-v2'

class QaSystem:
    def __init__(self, knowledge_base_dir="knowledge_base", api_key_override=None):
        print(f"INFO: (nlp_qa.py) Initializing QaSystem. Knowledge base directory: '{knowledge_base_dir}'")
        try:
            self.embedding_model = SentenceTransformer(MODEL_NAME)
            print("INFO: (nlp_qa.py) SentenceTransformer embedding model loaded successfully.")
        except Exception as e:
            print(f"CRITICAL ERROR: (nlp_qa.py) Failed to load SentenceTransformer model '{MODEL_NAME}'. Error: {e}")
            self.embedding_model = None
            return 

        self.knowledge_base_dir = knowledge_base_dir
        self.standards_data = {} 

        self.llm_client = None
        api_key_to_use = api_key_override
        if not api_key_to_use:
            api_key_to_use = os.getenv("OPENAI_API_KEY")
            if api_key_to_use:
                print("INFO: (nlp_qa.py) OpenAI API key found using environment variable 'OPENAI_API_KEY'.")
        
        if api_key_to_use:
            try:
                self.llm_client = OpenAI(api_key=api_key_to_use)
                print("INFO: (nlp_qa.py) OpenAI LLM client initialized successfully.")
            except Exception as e:
                print(f"ERROR: (nlp_qa.py) Failed to initialize OpenAI client. Error: {e}")
                self.llm_client = None 
        else:
            print("CRITICAL WARNING: (nlp_qa.py) OPENAI_API_KEY was not found. LLM Q&A features will be disabled.")

        if self.embedding_model:
            self._load_all_knowledge()
        else:
            print("ERROR: (nlp_qa.py) Cannot load knowledge base because embedding model failed to initialize.")

    def _load_standard_knowledge(self, standard_key, txt_filename, qna_filename):
        data = {"chunks": [], "embeddings": None, "qna": [], "qna_embeddings": None}
        
        txt_path = os.path.join(self.knowledge_base_dir, txt_filename)
        qna_path = os.path.join(self.knowledge_base_dir, qna_filename)

        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                standard_text = f.read()
            raw_chunks = chunk_text(standard_text) 
            processed_chunks = [preprocess_text(chunk) for chunk in raw_chunks if chunk.strip()]
            if processed_chunks:
                data["chunks"] = processed_chunks
                data["embeddings"] = self.embedding_model.encode(processed_chunks, convert_to_tensor=True)
        except FileNotFoundError:
            print(f"WARNING: (nlp_qa.py) Text file '{txt_filename}' not found in '{self.knowledge_base_dir}' for '{standard_key}'.")
        except Exception as e:
            print(f"ERROR: (nlp_qa.py) Error loading/processing text file '{txt_filename}' for '{standard_key}'. Error: {e}")

        try:
            with open(qna_path, 'r', encoding='utf-8') as f:
                loaded_qna = json.load(f) 
                data["qna"] = loaded_qna 
                if loaded_qna and isinstance(loaded_qna, list):
                    valid_qna_items = [item for item in loaded_qna if isinstance(item, dict) and 'question' in item and item['question']]
                    if valid_qna_items:
                        qna_questions_text = [preprocess_text(item['question']) for item in valid_qna_items]
                        if qna_questions_text: 
                            data["qna_embeddings"] = self.embedding_model.encode(qna_questions_text, convert_to_tensor=True)
                        data["qna"] = valid_qna_items
                    else: 
                        if loaded_qna:
                            print(f"WARNING: (nlp_qa.py) Q&A data in '{qna_filename}' for '{standard_key}' had no valid items. No Q&A embeddings.")
                        data["qna"] = []
                        data["qna_embeddings"] = None
                elif loaded_qna:
                    print(f"WARNING: (nlp_qa.py) Q&A data in '{qna_filename}' for '{standard_key}' is not a list. Skipping Q&A.")
                    data["qna"] = [] 
                    data["qna_embeddings"] = None
        except FileNotFoundError:
            print(f"INFO: (nlp_qa.py) Q&A file '{qna_filename}' not found for '{standard_key}'.")
            data["qna"] = [] 
            data["qna_embeddings"] = None
        except json.JSONDecodeError as e:
            print(f"ERROR: (nlp_qa.py) Invalid JSON in Q&A file '{qna_filename}' for '{standard_key}'. Error: {e}.")
            data["qna"] = []
            data["qna_embeddings"] = None
        except Exception as e:
            print(f"ERROR: (nlp_qa.py) Error loading Q&A file '{qna_filename}' for '{standard_key}'. Error: {e}")
            data["qna"] = [] 
            data["qna_embeddings"] = None
        
        self.standards_data[standard_key] = data
        
        num_chunks = len(data["chunks"])
        num_qna_pairs = len(data["qna"])
        qna_embed_status = "Successful" if data.get("qna_embeddings") is not None and num_qna_pairs > 0 else \
                           ("Not applicable (no Q&A pairs)" if num_qna_pairs == 0 else "Failed or no valid Qs")
        
        print(f"INFO: (nlp_qa.py) Loaded '{standard_key}'. Chunks: {num_chunks}. Q&A: {num_qna_pairs} (Embeddings: {qna_embed_status}).")

    def _load_all_knowledge(self):
        print("INFO: (nlp_qa.py) Starting to load all knowledge base standards...")
        standards_to_load = {
            "fas4": ("fas4_murabaha.txt", "fas4_qna.json"), "fas7": ("fas7_salam.txt", "fas7_qna.json"),
            "fas10": ("fas10_istisnaa.txt", "fas10_qna.json"), "fas28": ("fas28_murabaha_amend.txt", "fas28_qna.json"),
            "fas32": ("fas32_ijarah.txt", "fas32_qna.json"),
        }
        loaded_count = 0
        for key, (txt_file, qna_file) in standards_to_load.items():
            self._load_standard_knowledge(key, txt_file, qna_file)
            if self.standards_data.get(key) and \
               (self.standards_data[key].get("chunks") or self.standards_data[key].get("qna")):
                loaded_count +=1
        print(f"INFO: (nlp_qa.py) Finished loading all knowledge. {loaded_count}/{len(standards_to_load)} standards had some data.")

    def get_relevant_context(self, query_embedding, target_standard=None, top_k=3, threshold_text=0.50, threshold_qna=0.65):
        all_relevant_texts = []
        all_sources_info = [] 
        standards_to_search_keys = []
        processed_target_standard = None
        if target_standard:
            processed_target_standard = str(target_standard).lower().strip()
            if processed_target_standard == "all standards" or not processed_target_standard:
                processed_target_standard = None 
        if processed_target_standard and processed_target_standard in self.standards_data:
            standards_to_search_keys.append(processed_target_standard)
        elif not processed_target_standard: 
            standards_to_search_keys = list(self.standards_data.keys())
        for std_key in standards_to_search_keys:
            data_for_standard = self.standards_data.get(std_key)
            if not data_for_standard: continue
            if data_for_standard.get("chunks") and data_for_standard.get("embeddings") is not None:
                text_embeddings = data_for_standard["embeddings"]
                cos_scores_text = util.pytorch_cos_sim(query_embedding, text_embeddings)[0]
                top_text_indices = np.argsort(-cos_scores_text.cpu().numpy())[:top_k]
                for idx in top_text_indices:
                    idx = int(idx) 
                    score = cos_scores_text[idx].item() 
                    if score >= threshold_text:
                        all_relevant_texts.append(f"Context from {std_key.upper()} Text:\n{data_for_standard['chunks'][idx]}")
                        all_sources_info.append(f"Source: {std_key.upper()} Text Chunk (Similarity: {score:.2f})")
            if data_for_standard.get("qna") and data_for_standard.get("qna_embeddings") is not None:
                qna_embeddings = data_for_standard["qna_embeddings"]
                cos_scores_qna = util.pytorch_cos_sim(query_embedding, qna_embeddings)[0]
                for i, qna_item in enumerate(data_for_standard["qna"]):
                    similarity_to_curated_q = cos_scores_qna[i].item()
                    if similarity_to_curated_q >= threshold_qna:
                        all_relevant_texts.append(f"From {std_key.upper()} Q&A:\nQ: {qna_item['question']}\nA: {qna_item['answer']}")
                        all_sources_info.append(f"Source: {std_key.upper()} Curated Q&A ('{qna_item['question']}', Sim: {similarity_to_curated_q:.2f})")
        if not all_relevant_texts: return "", [] 
        unique_context_source_map = {}
        for i, context_text_item in enumerate(all_relevant_texts):
            if context_text_item not in unique_context_source_map:
                unique_context_source_map[context_text_item] = all_sources_info[i]
        final_contexts_list = list(unique_context_source_map.keys())
        final_sources_list = list(unique_context_source_map.values())
        effective_max_items = top_k 
        if len(standards_to_search_keys) > 1: effective_max_items = top_k + 2 
        limited_contexts = final_contexts_list[:effective_max_items]
        limited_sources = final_sources_list[:effective_max_items]
        final_context_str = "\n---\n".join(limited_contexts)
        return final_context_str, limited_sources 

    def answer_question_with_llm(self, query, target_standard=None):
        if not self.embedding_model: return "ERROR: Embedding model not available.", []
        if not self.llm_client: return "ERROR: LLM client not initialized.", []
        query_processed = preprocess_text(query)
        query_embedding = self.embedding_model.encode(query_processed, convert_to_tensor=True)
        context_str, sources_list_for_llm = self.get_relevant_context(query_embedding, target_standard=target_standard)
        if not context_str:
            std_name_disp = str(target_standard).upper() if target_standard and str(target_standard).lower() != "all standards" else "AAOIFI Standards"
            return f"I couldn't find information in {std_name_disp} for your query. Please rephrase.", []
        sys_msg_std_spec = str(target_standard).upper() if target_standard and str(target_standard).lower() != "all standards" else "relevant AAOIFI standards"
        sys_msg_content = (
            f"You are an AI assistant for AAOIFI Standards. Answer based *only* on the provided context "
            f"from {sys_msg_std_spec}. If not in context, say so. Do not invent. Be concise. "
            "Prioritize direct Q&A pairs from context if they answer the question."
        )
        user_prompt_content = f"Context from {sys_msg_std_spec}:\n---\n{context_str}\n---\nUser's Question: {query}\n\nBased *only* on the \"Context\" above, answer the \"User's Question\". If a Q&A in context answers it, use that. If info isn't there, state: \"The provided context does not contain a specific answer to this question.\""
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-3.5-turbo", 
                messages=[{"role": "system", "content": sys_msg_content}, {"role": "user", "content": user_prompt_content}],
                temperature=0.1, max_tokens=700 
            )
            llm_answer = response.choices[0].message.content.strip()
            return llm_answer, sources_list_for_llm 
        except Exception as e:
            print(f"ERROR: (nlp_qa.py) LLM API Error. Query: '{query}'. Error: {e}")
            return f"LLM Error: {e}", sources_list_for_llm
import json
import re
import os
from typing import Dict, List, Tuple
from openai import OpenAI
from dotenv import load_dotenv # Import load_dotenv

# Attempt to load .env file here in classifier.py itself,
# in case it's imported before app.py's load_dotenv() call.
# This provides a fallback for the global client.
load_dotenv() 

# Initialize the global OpenAI client carefully.
# This is a fallback if the class instance isn't given a key.
global_openai_client = None
_api_key_from_env_for_global = os.getenv("OPENAI_API_KEY")
if _api_key_from_env_for_global:
    try:
        global_openai_client = OpenAI(api_key=_api_key_from_env_for_global)
        print("Classifier Module: Global OpenAI client initialized from environment variable.")
    except Exception as e:
        print(f"Classifier Module Warning: Failed to initialize global OpenAI client from env var: {e}")
        global_openai_client = None # Ensure it's None on failure
else:
    print("Classifier Module Warning: OPENAI_API_KEY not found in environment. Global client not initialized.")


class StandardsClassifier:
    def __init__(self, 
                 standards_file: str, # Removed default to make it explicit from app.py
                 translations_file: str, # Removed default
                 fine_tuned_model_id: str = None,
                 openai_api_key: str = None):
        """
        Load standards, precompile regex, and set up model preferences.
        openai_api_key: If provided, this key will be used for this instance's client.
        """
        self.standards_file_path = standards_file
        self.translations_file_path = translations_file
        
        if openai_api_key:
            try:
                self.client = OpenAI(api_key=openai_api_key)
                print("StandardsClassifier Instance: Initialized with API key provided by caller.")
            except Exception as e:
                print(f"ERROR: StandardsClassifier Instance: Failed to initialize client with provided API key: {e}")
                # Fallback or raise an error if the key is invalid but provided
                if global_openai_client:
                    print("StandardsClassifier Instance: Falling back to global client due to error with provided key.")
                    self.client = global_openai_client
                else:
                    raise ValueError(f"Provided OpenAI API key is invalid and no global client available: {e}") from e
        elif global_openai_client:
            self.client = global_openai_client
            print("StandardsClassifier Instance: Using globally initialized OpenAI client (no key provided by caller).")
        else:
            # This case means no key was passed to constructor AND global client failed to initialize
            # (e.g. OPENAI_API_KEY was not in .env at all).
            print("CRITICAL ERROR: StandardsClassifier Instance: No API key provided and global client failed to initialize.")
            raise ValueError("OpenAI API key must be available either via constructor or OPENAI_API_KEY env var for global client.")

        # Load standards
        try:
            with open(self.standards_file_path, 'r', encoding='utf-8') as f:
                self.standards = json.load(f)
        except FileNotFoundError:
            print(f"CRITICAL ERROR: Standards file not found at {self.standards_file_path}")
            self.standards = {} # Or raise an error
        except json.JSONDecodeError:
            print(f"CRITICAL ERROR: Could not decode JSON from standards file {self.standards_file_path}")
            self.standards = {} # Or raise an error
        
        # Load translations
        self.translations = {}
        try:
            with open(self.translations_file_path, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Translations file not found at {self.translations_file_path}. Translations will be empty.")
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from translations file {self.translations_file_path}. Translations might be incomplete.")
        
        self.fine_tuned_model_id = fine_tuned_model_id
        
        # Precompile keywords and patterns
        self.all_keywords = {}
        if not self.standards:
             print("Warning: No standards loaded, keyword matching will be ineffective.")
        else:
            for std_id, std_data in self.standards.items():
                # Ensure std_data is a dictionary and contains expected keys
                if not isinstance(std_data, dict):
                    print(f"Warning: Standard data for {std_id} is not a dictionary. Skipping.")
                    continue

                en_keywords = []
                if 'key_concepts' in std_data and isinstance(std_data['key_concepts'], list):
                    en_keywords.extend(std_data['key_concepts'])
                if 'transaction_indicators' in std_data and isinstance(std_data['transaction_indicators'], list):
                    en_keywords.extend(std_data['transaction_indicators'])
                if 'accounting_entries' in std_data and isinstance(std_data['accounting_entries'], list):
                    en_keywords.extend(std_data['accounting_entries'])
                
                en_patterns = [re.compile(r'\b' + re.escape(str(kw).lower()) + r'\b', re.IGNORECASE) for kw in en_keywords if kw] # Ensure kw is not None
                
                ar_keywords = []
                # Safely access nested translation data
                ar_std_translation = self.translations.get('ar', {}).get('standards', {}).get(std_id, {})
                
                if isinstance(ar_std_translation, dict):
                    if 'key_concepts' in ar_std_translation and isinstance(ar_std_translation['key_concepts'], list):
                        ar_keywords.extend(ar_std_translation['key_concepts'])
                    elif 'name' in ar_std_translation and isinstance(ar_std_translation['name'], str):
                        ar_keywords.append(ar_std_translation['name'])
                    
                    # Specific Arabic keywords - consider a more robust way to manage these if they grow
                    # This mapping could be part of your translations.json or a separate config
                    specific_ar_keywords_map = {
                        'FAS4': ['مشاركة', 'شراكة', 'حقوق ملكية', 'مشروع مشترك', 'توزيع أرباح'],
                        'FAS7': ['سلم', 'بيع سلم', 'دفع مقدم', 'تسليم مستقبلي'],
                        'FAS10': ['استصناع', 'تصنيع', 'إنشاء', 'دفعات مرحلية'],
                        'FAS28': ['مرابحة', 'تكلفة زائد', 'أقساط', 'دفع مؤجل'],
                        'FAS32': ['إجارة', 'تأجير', 'حق استخدام', 'إجارة منتهية بالتمليك'],
                        'FAS20': ['عقار استثماري', 'إيراد إيجار', 'إدارة عقارات']
                    }
                    if std_id in specific_ar_keywords_map:
                         ar_keywords.extend(specific_ar_keywords_map[std_id])

                ar_patterns = [re.compile(re.escape(str(kw)), re.UNICODE) for kw in ar_keywords if kw] # Ensure kw is not None

                self.all_keywords[std_id] = {
                    'en_patterns': en_patterns, 
                    'ar_patterns': ar_patterns,
                    'weight': std_data.get('weight', 1.0) if isinstance(std_data.get('weight'), (int,float)) else 1.0
                }
    
    def detect_language(self, text: str) -> str:
        if not text or not isinstance(text, str): return 'en' # Default for empty or invalid input
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF') # Check for Arabic Unicode range
        # Consider a threshold for Arabic characters to be classified as Arabic
        return 'ar' if arabic_chars / max(len(text), 1) > 0.15 else 'en'


    def keyword_match(self, transaction_text: str) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        if not transaction_text: return scores

        language = self.detect_language(transaction_text)
        text_to_match = transaction_text.lower() if language == 'en' else transaction_text
        
        for std_id, kw_data in self.all_keywords.items():
            patterns_to_use = kw_data.get('ar_patterns' if language == 'ar' else 'en_patterns', [])
            num_matches = sum(1 for pattern in patterns_to_use if pattern.search(text_to_match))
            
            if num_matches > 0:
                # Simple scoring: 0.1 per match, capped or scaled later if needed.
                # The 'weight' from standards.json is applied here.
                base_score = num_matches * 0.1 
                scores[std_id] = base_score * kw_data.get('weight', 1.0)

        # Normalize keyword scores so they sum to 1 (if any scores exist)
        total_raw_score = sum(scores.values())
        if total_raw_score == 0: return {} # No keyword matches
        
        normalized_scores = {k: v / total_raw_score for k, v in scores.items()}
        return normalized_scores

    def _build_ai_prompt(self, transaction_text_to_fill: str, language: str) -> Tuple[str, str]:
        # Using a direct, safe approach for system message based on detected language
        if language == 'ar':
            system_message_content = "أنت خبير في معايير المحاسبة المالية (FAS) الصادرة عن هيئة المحاسبة والمراجعة للمؤسسات المالية الإسلامية..." # Truncated for brevity
            prompt_header = "الرجاء تحليل معاملة التمويل الإسلامي التالية...\nمثال للإخراج: {{ \"FAS28\": 0.6, ... }}\n\n"
            standards_list_header = "قائمة المعايير المحتملة:\n"
            transaction_header = "\nتفاصيل المعاملة:\n'''{transaction_text}'''" # Placeholder
            output_json_header = "\n\nكائن JSON الخاص بالإخراج:\n"
        else: # Default to English
            system_message_content = "You are an expert in AAOIFI Financial Accounting Standards (FAS)..." # Truncated
            prompt_header = "Please analyze the following Islamic finance transaction...\nExample output: {{ \"FAS28\": 0.6, ... }}\n\n"
            standards_list_header = "List of possible standards:\n"
            transaction_header = "\nTransaction details:\n'''{transaction_text}'''" # Placeholder
            output_json_header = "\n\nYour JSON output:\n"

        # Build standards list section dynamically
        standards_list_items = []
        for std_id, std_data_master in self.standards.items():
            # Get base name (usually English)
            name_en = std_data_master.get("name", f"Standard {std_id}")
            desc_en_short = (std_data_master.get("description", "")[:100] + '...') if std_data_master.get("description") else ""

            if language == 'ar':
                # Attempt to get Arabic translation for name and description
                ar_std_trans = self.translations.get('ar', {}).get('standards', {}).get(std_id, {})
                name_display = ar_std_trans.get('name', name_en) # Fallback to English name if AR not found
                desc_ar_short = (ar_std_trans.get('description', desc_en_short)[:100] + '...') if ar_std_trans.get('description') else desc_en_short
                item_str = f"- {std_id}: {name_display} (الوصف: {desc_ar_short})"
            else: # English
                item_str = f"- {std_id}: {name_en} (Description: {desc_en_short})"
            standards_list_items.append(item_str)
        
        standards_section_str = standards_list_header + "\n".join(standards_list_items)

        # Construct the user prompt using f-string for placeholder substitution
        # Ensure the actual transaction text is correctly substituted here
        user_prompt_content_template = (
            prompt_header +
            standards_section_str +
            transaction_header + # This has the {transaction_text} placeholder
            output_json_header
        )
        user_prompt_content = user_prompt_content_template.format(transaction_text=transaction_text_to_fill)
        
        return system_message_content, user_prompt_content

    def _call_openai_api(self, model_to_use: str, system_message: str, user_prompt: str, context_for_error_msg: str) -> Dict[str, float]:
        if not self.client: # Should not happen if constructor validation is good
            print(f"Error: OpenAI client not initialized in _call_openai_api for {context_for_error_msg}.")
            return {}
        try:
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, # Requires newer models like gpt-3.5-turbo-1106+ or gpt-4-turbo
                temperature=0.2 # Low temperature for more deterministic output
            )
            result_content = response.choices[0].message.content
            
            # Attempt to clean if wrapped in markdown code block (common from models)
            if result_content:
                match = re.search(r"```json\s*(\{.*?\})\s*```", result_content, re.DOTALL)
                if match:
                    result_content = match.group(1)
                else: # If not markdown, try to find JSON directly, strip leading/trailing whitespace
                    result_content = result_content.strip()

            if not result_content:
                print(f"Warning: AI ({context_for_error_msg}, model {model_to_use}) returned empty content.")
                return {}

            result_dict = json.loads(result_content)
            # Filter for valid standard IDs and numeric scores
            parsed_scores = {
                k: float(v) for k, v in result_dict.items() 
                if k in self.standards and isinstance(v, (int, float))
            }
            
            # Renormalize if scores don't sum to 1.0 (within a tolerance)
            total_score = sum(parsed_scores.values())
            if parsed_scores and (abs(total_score - 1.0) > 0.05 and total_score != 0):
                print(f"Warning: AI scores from {context_for_error_msg} for model {model_to_use} sum to {total_score} (not 1.0). Renormalizing.")
                return {k: v / total_score for k, v in parsed_scores.items()}
            elif not parsed_scores:
                print(f"Warning: AI ({context_for_error_msg}, model {model_to_use}) returned no valid/recognized standard scores from: {result_content[:200]}")
                return {}
            return parsed_scores

        except json.JSONDecodeError as e:
            print(f"AI JSON Decode Error ({context_for_error_msg}, model {model_to_use}): {e}. Received: '{result_content[:300]}...'")
            return {}
        except Exception as e: # Catch other OpenAI API errors or unexpected issues
            print(f"Generic AI API Error ({context_for_error_msg}, model {model_to_use}): {e}")
            return {}

    def analyze_with_finetuned_or_default_ai(self, transaction_text: str) -> Dict[str, float]:
        language = self.detect_language(transaction_text)
        system_message, user_prompt = self._build_ai_prompt(transaction_text, language)
        
        # Prioritize fine-tuned model if ID is provided, otherwise use a strong default
        model_id = self.fine_tuned_model_id if self.fine_tuned_model_id else "gpt-3.5-turbo-1106" # or gpt-4-turbo if budget allows
        context = "Fine-tuned Model" if self.fine_tuned_model_id else "Default AI Model"
        print(f"Analyzing with {context}: {model_id}")
        
        return self._call_openai_api(model_id, system_message, user_prompt, context)

    def analyze_with_general_prompted_ai(self, transaction_text: str) -> Dict[str, float]:
        language = self.detect_language(transaction_text)
        system_message, user_prompt = self._build_ai_prompt(transaction_text, language)
        
        model_id = "gpt-3.5-turbo-1106" # A capable general model, or gpt-4-turbo
        print(f"Analyzing with General Prompted AI Model: {model_id}")

        return self._call_openai_api(model_id, system_message, user_prompt, "General Prompted AI")

    def classify_transaction(
        self, 
        transaction_text: str,
        weight_keyword: float = 0.20,
        weight_finetuned_ai: float = 0.35, 
        weight_general_ai: float = 0.45 # Ensure these sum to 1.0
    ) -> List[Tuple[str, float]]:

        # Basic validation of weights
        if abs(weight_keyword + weight_finetuned_ai + weight_general_ai - 1.0) > 0.001:
            print("Warning: Sum of classification weights is not 1.0. Normalization will occur, but review weights.")

        print(f"\n--- Classifying Transaction (first 50 chars): '{transaction_text[:50].strip()}...' ---")
        
        keyword_scores = self.keyword_match(transaction_text)
        print(f"Keyword Match Scores (Normalized): {json.dumps(keyword_scores, indent=2)}")

        # Scores from AI (fine-tuned or default high-capability)
        finetuned_ai_scores = self.analyze_with_finetuned_or_default_ai(transaction_text)
        print(f"Fine-tuned/Default AI Scores (Normalized within AI method): {json.dumps(finetuned_ai_scores, indent=2)}")
        
        # Scores from general prompted AI (e.g., for robustness or broader perspective)
        general_ai_scores = self.analyze_with_general_prompted_ai(transaction_text)
        print(f"General Prompted AI Scores (Normalized within AI method): {json.dumps(general_ai_scores, indent=2)}")

        # Combine scores
        all_relevant_standards_ids = set(keyword_scores.keys()) | set(finetuned_ai_scores.keys()) | set(general_ai_scores.keys())
        if not all_relevant_standards_ids: # If all methods returned empty
             print("No relevant standards identified from any source.")
             return []

        combined_weighted_scores = {}
        for std_id in all_relevant_standards_ids:
            score_from_kw = keyword_scores.get(std_id, 0.0)
            score_from_ft_ai = finetuned_ai_scores.get(std_id, 0.0)
            score_from_gen_ai = general_ai_scores.get(std_id, 0.0)
            
            # Weighted sum
            final_score = (
                (score_from_kw * weight_keyword) +
                (score_from_ft_ai * weight_finetuned_ai) +
                (score_from_gen_ai * weight_general_ai)
            )
            # Only include if there's some score contribution
            if final_score > 0.0001: # Small threshold to avoid noise
                 combined_weighted_scores[std_id] = final_score
        
        if not combined_weighted_scores:
            print("No standards scored above threshold after combining sources.")
            return []

        # Final normalization of the combined weighted scores (so the final list sums to 1.0)
        total_final_score = sum(combined_weighted_scores.values())
        if total_final_score == 0: # Should be caught by the > 0.0001 check, but for safety
             return []

        fully_normalized_scores = {
            std_id: score / total_final_score for std_id, score in combined_weighted_scores.items()
        }
        print(f"Final Combined & Normalized Scores: {json.dumps(fully_normalized_scores, indent=2)}")
        print("--- Classification Process Finished ---\n")

        # Sort by score descending and return
        return sorted(fully_normalized_scores.items(), key=lambda item: item[1], reverse=True)


    def explain_classification(self, transaction_text: str, top_standards_scores: List[Tuple[str, float]]) -> Dict[str, str]:
        # Uses pre-loaded self.standards and self.translations
        # Uses self.all_keywords for keyword highlighting in explanations
        
        if not transaction_text or not top_standards_scores:
            return {}

        language = self.detect_language(transaction_text)
        explanations_dict: Dict[str, str] = {}
        
        for std_id, score_value in top_standards_scores:
            if std_id not in self.standards:
                print(f"Warning (Explain): Standard ID {std_id} not in loaded standards.")
                continue

            master_std_data = self.standards[std_id]
            # Base name/description (usually English or primary language of standards.json)
            base_std_name = master_std_data.get("name", f"Standard {std_id}")
            base_std_desc = master_std_data.get("description", "No description provided.")

            # Get translated name/description for display
            current_lang_std_translation = self.translations.get(language, {}).get('standards', {}).get(std_id, {})
            display_name = current_lang_std_translation.get('name', base_std_name)
            display_desc = current_lang_std_translation.get('description', base_std_desc)
            
            # Keyword highlighting logic
            text_for_keyword_match = transaction_text.lower() if language == 'en' else transaction_text
            keywords_data_for_std_id = self.all_keywords.get(std_id, {})
            patterns = keywords_data_for_std_id.get('ar_patterns' if language == 'ar' else 'en_patterns', [])
            
            matched_kws = set() # Use a set to store unique matched keywords
            for pattern_re in patterns:
                # The pattern itself is already compiled, e.g., re.compile(r'\bmurabaha\b')
                # pattern_re.pattern would give r'\bmurabaha\b'
                # We need to extract the actual keyword string
                # This assumes simple keyword patterns, not complex regexes
                keyword_in_pattern = pattern_re.pattern.replace(r'\b', '').replace('\\', '')
                if language == 'ar': # Arabic patterns are usually direct strings
                    keyword_in_pattern = pattern_re.pattern

                if pattern_re.search(text_for_keyword_match):
                    matched_kws.add(keyword_in_pattern.strip())
            
            matched_keywords_display_str = ', '.join(list(matched_kws)) if matched_kws else ""

            # Constructing the explanation string
            reasoning_parts = []
            if language == 'ar':
                intro = "يُعتبر هذا المعيار مهماً لهذه المعاملة "
                if matched_keywords_display_str:
                    reasoning_parts.append(f"{intro} بسبب وجود كلمات رئيسية ذات صلة مثل: '{matched_keywords_display_str}'.")
                else: # If no keywords matched, assume AI was the primary driver (or other logic)
                    reasoning_parts.append(f"{intro} بناءً على تحليل الذكاء الاصطناعي الذي يرى تشابهات مع خصائص المعيار.")
                reasoning_parts.append(f"يُظهر هذا المعيار صلة بالمعاملة بنسبة {score_value*100:.0f}%.")
            else: # English
                intro = "This standard is relevant to the transaction "
                if matched_keywords_display_str:
                    reasoning_parts.append(f"{intro} due to matching keywords such as: '{matched_keywords_display_str}'.")
                else:
                    reasoning_parts.append(f"{intro} based on AI analysis identifying similarities to the standard's characteristics.")
                reasoning_parts.append(f"It shows a {score_value*100:.0f}% relevance to the transaction.")
            
            explanation_html = f"<h4>{display_name} ({std_id})</h4>"
            explanation_html += f"<p><strong>{'الوصف' if language == 'ar' else 'Description'}:</strong> {display_desc}</p>"
            explanation_html += f"<p><strong>{'المنطق' if language == 'ar' else 'Reasoning'}:</strong> {' '.join(reasoning_parts)}</p>"
            # You can add more detailed explanation here, perhaps from a specific AI call for explanation.

            explanations_dict[std_id] = explanation_html
            
        return explanations_dict


if __name__ == "__main__":
    # This ensures .env is loaded for the __main__ block execution specifically.
    # It's good practice for standalone script testing.
    from dotenv import load_dotenv
    load_dotenv(override=True) # Override to ensure it re-reads if called before

    main_openai_api_key = os.getenv("OPENAI_API_KEY")
    if not main_openai_api_key:
        print("CRITICAL: OPENAI_API_KEY environment variable not set for __main__ block. Cannot run example.")
    else:
        print(f"__main__: OPENAI_API_KEY is set (masked: sk-...{main_openai_api_key[-4:]}). Proceeding.")
        
        # Example relative paths from the project root where this script is in models/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Assumes models/ is one level down from root
        main_standards_file = os.path.join(project_root, "data", "standards.json")
        main_translations_file = os.path.join(project_root, "data", "translations.json")

        main_fine_tuned_id = os.getenv("FINE_TUNED_MODEL_ID") 
        if main_fine_tuned_id:
            print(f"__main__: Using FINE_TUNED_MODEL_ID: {main_fine_tuned_id}")
        else:
            print("__main__: FINE_TUNED_MODEL_ID not set. Using default model logic in classifier.")

        classifier_instance = StandardsClassifier(
            standards_file=main_standards_file, 
            translations_file=main_translations_file,
            fine_tuned_model_id=main_fine_tuned_id,
            openai_api_key=main_openai_api_key # Explicitly pass the key
        )

        example_en_transaction = """
        A corporation enters into a Murabaha agreement with an Islamic bank to finance the purchase of new manufacturing equipment. 
        The equipment costs $500,000. The bank purchases the equipment and sells it to the corporation for $550,000, 
        payable in 24 monthly installments. The bank clearly discloses its cost and profit margin. 
        This transaction involves deferred payment sale of an asset.
        """
        
        example_ar_transaction = """
        تدخل شركة في اتفاقية مرابحة مع بنك إسلامي لتمويل شراء معدات تصنيع جديدة.
        تكلفة المعدات 500,000 دولار. يشتري البنك المعدات ويبيعها للشركة مقابل 550,000 دولار،
        تُسدد على 24 قسطًا شهريًا. يفصح البنك بوضوح عن تكلفته وهامش ربحه.
        تتضمن هذه المعاملة بيع أصل بدفع مؤجل.
        """
        
        test_transactions = {
            "English Equipment Murabaha": example_en_transaction,
            "Arabic Equipment Murabaha": example_ar_transaction
        }
        
        custom_weights = {"keyword": 0.15, "finetuned_ai": 0.40, "general_ai": 0.45}
        print(f"\n__main__: Testing with weights - Keyword: {custom_weights['keyword']}, FineTuned/DefaultAI: {custom_weights['finetuned_ai']}, GeneralAI: {custom_weights['general_ai']}")

        for desc, text in test_transactions.items():
            print(f"\n===== Testing: {desc} =====")
            detected_lang = classifier_instance.detect_language(text)
            print(f"Detected Language: {detected_lang}")
            
            classified_results = classifier_instance.classify_transaction(
                text,
                weight_keyword=custom_weights['keyword'],
                weight_finetuned_ai=custom_weights['finetuned_ai'],
                weight_general_ai=custom_weights['general_ai']
            )
            
            if not classified_results:
                print("No standards identified for this transaction.")
                continue

            print("\nClassification Results (Top relevant standards):")
            for std_id_res, score_res in classified_results[:3]: # Show top 3 for brevity
                std_name_res = classifier_instance.standards.get(std_id_res, {}).get('name', 'Unknown Standard')
                print(f"  - {std_name_res} ({std_id_res}): {score_res*100:.2f}%")

            # Generate explanations for the classified results
            explanations_for_results = classifier_instance.explain_classification(text, classified_results)
            print("\nExplanations for identified standards:")
            for std_id_exp, explanation_text in explanations_for_results.items():
                # Quick strip of HTML for console readability in __main__
                console_explanation = re.sub('<[^<]+?>', '', explanation_text).replace('\n', ' ')
                print(f"  For {std_id_exp}:\n    {console_explanation}\n")
            print("=" * 30)
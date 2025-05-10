from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv # Ensure this is at the very top
import os
import json

load_dotenv() # <<<< CRITICAL: Load environment variables FIRST

# Now import your classifier, it can try to load .env again, but app.py's load is primary for its own os.getenv calls
try:
    from models.classifier import StandardsClassifier
except ImportError as e:
    print(f"ERROR: Could not import StandardsClassifier: {e}. Make sure models/classifier.py exists and is accessible.")
    # Dummy class for app to run without full classifier logic (for frontend testing)
    class StandardsClassifier:
        def __init__(self, *args, **kwargs): print("Warning: Using DUMMY StandardsClassifier due to import error.")
        def classify_transaction(self, text, **kwargs): print(f"Dummy classify: {text}"); return [] # Return empty list
        def explain_classification(self, text, results, **kwargs): print(f"Dummy explain: {text}"); return {} # Return empty dict
    # You might want to 'raise' the error in production or if classifier is essential for app to start
    # raise

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}) # For development, adjust for production
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_flask_secret_key_for_development")

# --- Configuration & Initialization ---
# Get API key AFTER load_dotenv() has run
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FINE_TUNED_MODEL_ID = os.getenv("FINE_TUNED_MODEL_ID")

if not OPENAI_API_KEY:
    print("CRITICAL Warning: OPENAI_API_KEY environment variable is not set or loaded. OpenAI calls will likely fail.")
else:
    print(f"app.py: OpenAI API Key found (masked: sk-...{OPENAI_API_KEY[-4:] if len(OPENAI_API_KEY) > 4 else 'SHORT'}).")


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STANDARDS_FILE = os.path.join(DATA_DIR, "standards.json")
TRANSLATIONS_FILE = os.path.join(DATA_DIR, "translations.json")
EXAMPLES_FILE = os.path.join(DATA_DIR, "examples.json")

# Instantiate classifier, passing the API key
# This ensures the classifier's instance client uses the key loaded by app.py
classifier = StandardsClassifier(
    standards_file=STANDARDS_FILE,
    translations_file=TRANSLATIONS_FILE,
    fine_tuned_model_id=FINE_TUNED_MODEL_ID,
    openai_api_key=OPENAI_API_KEY # Explicitly pass the API key
)

try:
    with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
        examples_data_list = json.load(f)
except Exception as e:
    print(f"Error loading examples file ({EXAMPLES_FILE}): {e}. Examples list will be empty.")
    examples_data_list = []

try:
    with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
        translations_data_all_langs = json.load(f)
except Exception as e:
    print(f"Error loading translations file ({TRANSLATIONS_FILE}): {e}. Translations functionality will be impacted.")
    translations_data_all_langs = {
        "en": {"error_loading_translations": "Critical: Main translations file could not be loaded."},
        "ar": {"error_loading_translations": "خطأ جسيم: لم يتم تحميل ملف الترجمة الرئيسي."}
    }

# --- API Endpoints ---
@app.route('/api/translations/<language>')
def get_translations_for_lang_route(language):
    lang_code = language.lower()
    lang_data = translations_data_all_langs.get(lang_code)
    
    if lang_data:
        return jsonify(lang_data)
    
    # Fallback to English if requested language is not found
    print(f"Warning: Translations for '{lang_code}' not found. Falling back to 'en'.")
    fallback_lang_data = translations_data_all_langs.get('en', {})
    if not fallback_lang_data and lang_code != 'en': # If even 'en' is missing and it wasn't 'en' requested
         return jsonify({"error": f"Translations for '{lang_code}' and fallback 'en' are missing."}), 404
    return jsonify(fallback_lang_data)


@app.route('/api/examples')
def get_all_examples_route():
    return jsonify(examples_data_list)


def process_analysis_request_logic(transaction_text, lang_code_input):
    current_lang_code = lang_code_input.lower() if lang_code_input.lower() in translations_data_all_langs else 'en'
    current_translations_for_error_msgs = translations_data_all_langs.get(current_lang_code, {})

    if not transaction_text or not transaction_text.strip():
        error_msg_key = "error_no_transaction_text" 
        default_error_msg = "Transaction text is required for analysis."
        error_message = current_translations_for_error_msgs.get(error_msg_key, default_error_msg)
        return {"error": error_message}, 400

    # Define weights for different classification methods
    weights = { 
        "weight_keyword": 0.25, 
        "weight_finetuned_ai": 0.35, 
        "weight_general_ai": 0.40 
    }
    
    try:
        # Get raw scores from the classifier
        classified_scores_tuples = classifier.classify_transaction(
            transaction_text,
            weight_keyword=weights["weight_keyword"],
            weight_finetuned_ai=weights["weight_finetuned_ai"],
            weight_general_ai=weights["weight_general_ai"]
        )
        # Get explanations based on these scores
        explanations_dict = classifier.explain_classification(transaction_text, classified_scores_tuples)

    except Exception as e: # Catch broader errors from classifier methods
        print(f"Error during classification or explanation process: {e}")
        error_msg_key = "error_classification_failed"
        default_error_msg = "An internal error occurred during analysis."
        error_message = current_translations_for_error_msgs.get(error_msg_key, default_error_msg)
        # Include details if in debug mode or for logging
        return {"error": error_message, "details": str(e) if app.debug else None}, 500

    # Load master standards data for names/descriptions for formatting the results
    try:
        with open(STANDARDS_FILE, 'r', encoding="utf-8") as f:
            standards_master_data = json.load(f)
    except Exception as e:
        print(f"Critical Error loading standards master file ({STANDARDS_FILE}) in process_analysis: {e}")
        standards_master_data = {} 

    formatted_results_list = []
    for std_id, score_value in classified_scores_tuples:
        standard_info_from_master = standards_master_data.get(std_id, {})
        
        # Base name/description (usually English or from standards.json primary lang)
        base_name_from_master = standard_info_from_master.get("name", f"Standard {std_id}")
        base_desc_from_master = standard_info_from_master.get("description", "No description available.")

        # Attempt to get translated name/description for the current display language (current_lang_code)
        # This uses the main translations_data_all_langs for the UI display part
        display_lang_translations_for_standards = translations_data_all_langs.get(current_lang_code, {}).get('standards', {})
        std_specific_display_translation = display_lang_translations_for_standards.get(std_id, {})
        
        display_name = std_specific_display_translation.get('name', base_name_from_master)
        display_description = std_specific_display_translation.get('description', base_desc_from_master)
        
        formatted_results_list.append({
            "standard_id": std_id,
            "name": display_name,
            "description": display_description,
            "score": round(score_value * 100, 2), # Assuming score_value is 0-1 from classifier
            "explanation": explanations_dict.get(std_id, "") # Get corresponding explanation
        })
    
    # Results are already sorted by classifier's classify_transaction method
    return formatted_results_list, 200


@app.route('/api/analyze', methods=['POST'])
def api_analyze_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload. Missing 'transaction_text' or 'language'."}), 400
        
    transaction_text = data.get('transaction_text', '')
    lang_code_input = data.get('language', 'en').lower() # Default to 'en', ensure lowercase
    
    # Validate if the language is one of the supported ones by translations_data_all_langs keys
    if lang_code_input not in translations_data_all_langs:
        print(f"Warning: Language '{lang_code_input}' provided in analyze request is not in loaded translations. Defaulting to 'en'.")
        lang_code_input = 'en' # Fallback
        
    results_data_payload, status_code_from_process = process_analysis_request_logic(transaction_text, lang_code_input)
    
    if status_code_from_process != 200: # An error occurred
         return jsonify(results_data_payload), status_code_from_process # Payload contains the error dict

    return jsonify({
        "transaction_text": transaction_text,
        "results": results_data_payload # This is the list of formatted standard objects
    }), 200


if __name__ == '__main__':
    print(f"Flask app is attempting to start on http://0.0.0.0:5000 (accessible on your network)")
    if FINE_TUNED_MODEL_ID:
        print(f"Using Fine-Tuned Model ID if specified in classifier: {FINE_TUNED_MODEL_ID}")
    else:
        print("FINE_TUNED_MODEL_ID is not set in .env; classifier will use its default or base model logic.")
    
    # The host='0.0.0.0' makes the server accessible from other devices on the same network.
    # For purely local development, '127.0.0.1' is also fine.
    app.run(debug=True, host='0.0.0.0', port=5000)
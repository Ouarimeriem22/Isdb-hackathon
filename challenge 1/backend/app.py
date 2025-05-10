# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from modules.use_case_parser import UseCaseParser
from modules.calculations import (
    calculate_ijarah_mbt_initial_recognition,
    calculate_zakat_on_cash_savings,
    calculate_zakat_on_business_assets, # Corrected from previous fix
    calculate_salam_transaction_implications,
    # calculate_istisnaa_percentage_of_completion, # <<< CHANGE THIS LINE
    calculate_istisnaa_contract_implications,    # <<< TO THIS
    calculate_murabaha_from_params
)

app = Flask(__name__)
CORS(app)
if not app.debug: app.logger.setLevel(logging.INFO)
else: app.logger.setLevel(logging.DEBUG)

parser_instance = None
print("INFO: (app.py) Attempting to initialize UseCaseParser...")
try:
    parser_instance = UseCaseParser()
    if parser_instance and parser_instance.llm_client:
        print("INFO: (app.py) UseCaseParser initialized with LLM client OK.")
    else:
        print("WARNING: (app.py) UseCaseParser LLM client NOT available (check API key).")
except Exception as e:
    print(f"FATAL ERROR (app.py UseCaseParser setup): {e}")
    import traceback; traceback.print_exc()
    parser_instance = None

@app.route('/api/analyze-scenario', methods=['POST'])
def analyze_scenario_endpoint():
    if not parser_instance or not parser_instance.llm_client:
        app.logger.error("/api/analyze-scenario: Parser or LLM client unavailable.")
        return jsonify({"error": "AI scenario analysis service unavailable. Try later."}), 503

    data = request.get_json()
    if not data or 'scenario_text' not in data or not data['scenario_text'].strip():
        return jsonify({"error": "Invalid request: Missing or empty 'scenario_text'."}), 400

    scenario_text = data['scenario_text']
    app.logger.info(f"/api/analyze-scenario: Received text: '{scenario_text[:100]}...'")

    extracted_data, error_msg_extraction = parser_instance.extract_parameters_from_scenario(scenario_text)
    if error_msg_extraction:
        app.logger.error(f"Parameter extraction failed: {error_msg_extraction}")
        return jsonify({"error": f"Failed to parse scenario: {error_msg_extraction}"}), 400

    if not extracted_data or "transaction_type" not in extracted_data or "parameters" not in extracted_data:
        app.logger.error(f"LLM extraction incomplete. Data: {extracted_data}")
        return jsonify({"error": "Could not determine transaction type or parameters."}), 400

    transaction_type = extracted_data.get("transaction_type", "Unknown").strip()
    parameters = extracted_data.get("parameters", {})
    app.logger.info(f"Extracted: Type='{transaction_type}', Params='{str(parameters)[:100]}...'")

    calculation_result, error_msg_calculation = None, None

    # Dispatch based on transaction_type (case-insensitive for robustness)
    if transaction_type.lower() == "ijarah mbt":
        calculation_result, error_msg_calculation = calculate_ijarah_mbt_initial_recognition(parameters)
    elif transaction_type.lower() == "zakat on cash savings":
        calculation_result, error_msg_calculation = calculate_zakat_on_cash_savings(parameters)
    elif transaction_type.lower() == "zakat on business assets":
        calculation_result, error_msg_calculation = calculate_zakat_on_business_assets(parameters)
    elif transaction_type.lower() == "salam":
         calculation_result, error_msg_calculation = calculate_salam_transaction_implications(parameters)
    # elif transaction_type.lower() == "istisnaa poc" or "istisna'a" in transaction_type.lower(): # <<< OLD DISPATCH
    #      calculation_result, error_msg_calculation = calculate_istisnaa_percentage_of_completion(parameters)
    elif "istisna" in transaction_type.lower(): # <<< CORRECTED DISPATCH (matches the one in previous calculations.py update)
         calculation_result, error_msg_calculation = calculate_istisnaa_contract_implications(parameters)
    elif transaction_type.lower() == "murabaha":
         calculation_result, error_msg_calculation = calculate_murabaha_from_params(parameters)
    else:
        error_msg_calculation = f"Transaction type '{transaction_type}' not recognized or calculation not supported."

    if error_msg_calculation:
        app.logger.warning(f"Calc error type '{transaction_type}': {error_msg_calculation}")
        return jsonify({
            "error": error_msg_calculation, "extracted_transaction_type": transaction_type,
            "extracted_parameters": parameters }), 422

    if calculation_result:
        return jsonify({
            "extracted_transaction_type": transaction_type,
            "extracted_parameters_used": parameters,
            "calculation_output": calculation_result
        })
    else:
        app.logger.error(f"No result/error for '{transaction_type}'. Params: {parameters}")
        return jsonify({"error": "Unexpected issue in calculation module."}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    llm_status = "Unknown"
    if parser_instance: llm_status = "Connected" if parser_instance.llm_client else "Not Connected/Error"
    else: llm_status = "Parser Not Initialized"
    return jsonify({"status": "Backend running", "llm_client_status_for_parser": llm_status})

if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 3004))
    print(f"INFO: (app.py) Scenario Analysis server starting on http://0.0.0.0:{port}/")
    app.run(debug=True, host='0.0.0.0', port=port)
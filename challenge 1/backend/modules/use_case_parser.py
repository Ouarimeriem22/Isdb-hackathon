# backend/modules/use_case_parser.py
from openai import OpenAI
import json
import os

class UseCaseParser:
    def __init__(self, api_key=None):
        # ... (init code - no change) ...
        self.llm_client = None
        api_key_to_use = api_key or os.getenv("OPENAI_API_KEY")
        if api_key_to_use:
            try:
                self.llm_client = OpenAI(api_key=api_key_to_use)
                print("INFO: (UseCaseParser) OpenAI client initialized.")
            except Exception as e:
                print(f"ERROR: (UseCaseParser) Failed to initialize OpenAI client: {e}")
        else:
            print("WARNING: (UseCaseParser) No OpenAI API key provided or found in env. Parser will not function.")

    def extract_parameters_from_scenario(self, scenario_text: str):
        if not self.llm_client:
            return None, "LLM client not initialized in UseCaseParser."

        prompt = f"""
        You are an AI expert specializing in AAOIFI standards and Islamic finance accounting.
        Your task is to meticulously analyze the provided Islamic finance scenario text and extract key information.

        General Instructions for all transaction types:
        1. Identify the primary Islamic finance transaction type (e.g., "Ijarah MBT", "Murabaha", "Salam", "Istisna'a", "Zakat on Business Assets", "Zakat on Cash Savings").
        2. Extract all relevant financial figures. **CRITICAL: Financial figures (prices, costs, quantities, amounts) MUST be extracted as PURE NUMBERS (integers or decimals), removing any currency symbols (like $, USD, EUR), commas (like in 1,000), and units (like tons, kg, years) directly from the value. For example, "1,000 tons" should result in a value of 1000 for quantity. "USD 300" should result in a value of 300.**
        3. Extract dates. If possible, format them as YYYY-MM-DD. If ambiguous, provide the date text as is.
        4. Extract terms (e.g., lease term in years or months, as a number).
        5. Extract names of parties involved and descriptions of assets.
        6. Output the results strictly in JSON format. The JSON must have a top-level key "transaction_type" (string) and a nested object "parameters".
        7. Under "parameters", use consistent snake_case keys. Examples: `contract_date`, `asset_description`, `quantity`, `price_per_unit`, `currency`, `lease_term_years`, `total_asset_cost`.

        {self.get_specific_instructions_for_llm()} 

        Scenario Text to Analyze:
        ---
        {scenario_text}
        ---
        
        Strictly output JSON only, with no surrounding text or markdown:
        """
        print("INFO: (UseCaseParser) Sending scenario to LLM for parameter extraction...")
        # print(f"DEBUG: (UseCaseParser) Full prompt being sent to LLM:\n{prompt}") # For deep debugging of prompt
        print(f"DEBUG: (UseCaseParser) Prompt being sent to LLM (first 1500 chars of prompt for brevity in log):\n{prompt[:1500]}...")
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-3.5-turbo-0125", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0, 
                response_format={"type": "json_object"} 
            )
            extracted_json_str = response.choices[0].message.content 
            print(f"DEBUG: (UseCaseParser) LLM raw JSON string response: {extracted_json_str}")
            
            parsed_data = json.loads(extracted_json_str)

            if not isinstance(parsed_data, dict) or "transaction_type" not in parsed_data or "parameters" not in parsed_data:
                raise ValueError("LLM output missing required top-level keys: 'transaction_type' or 'parameters', or is not a dictionary.")
            if not isinstance(parsed_data.get("parameters"), dict):
                 raise ValueError("LLM output 'parameters' field is missing or not a dictionary.")

            print("INFO: (UseCaseParser) Successfully parsed parameters from LLM.")
            return parsed_data, None
        except json.JSONDecodeError as e:
            error_message = f"Failed to decode JSON from LLM response: {e}. Response was: {extracted_json_str}"
            print(f"ERROR: (UseCaseParser) {error_message}")
            return None, error_message
        except ValueError as e: 
            error_message = f"LLM output validation error: {e}. Response was: {extracted_json_str if 'extracted_json_str' in locals() else 'Response not captured before error'}"
            print(f"ERROR: (UseCaseParser) {error_message}")
            return None, error_message
        except Exception as e: 
            error_message = f"LLM API call or other processing failed: {e}"
            print(f"ERROR: (UseCaseParser) {error_message}")
            import traceback
            traceback.print_exc() 
            return None, error_message

    def get_specific_instructions_for_llm(self):
        # Moved specific instructions here to keep the main prompt cleaner
        return """
        Specific Instructions for Ijarah MBT:
        - For costs (like asset purchase), if multiple components are mentioned (e.g., purchase price, import tax, freight), list them individually as an array of objects under "asset_initial_cost_components", each object having "type" (e.g., "purchase_price", "import_tax") and "value" (as a number). If only a total cost is given, use "total_asset_cost".
        - Example Keys: `commencement_date`, `lessee_name`, `lessor_name`, `asset_description`, `asset_initial_cost_components`, `total_asset_cost`, `lease_term_years`, `yearly_rental`, `payment_frequency`, `ownership_transfer_option_price`, `expected_residual_value_at_lease_end`.

        Specific Instructions for Murabaha:
        - Example Keys: `contract_date`, `financier_name`, `client_name`, `asset_description`, `asset_cost_to_seller` (or `asset_cost_to_bank`), `profit_margin_percentage` (as a decimal, e.g., 0.10 for 10%), `profit_amount_fixed`, `sale_price_to_customer`, `number_of_installments`, `down_payment_amount`, `currency`.

        Specific Instructions for Salam:
        - **CRITICAL for Salam:** Extract `quantity` as a PURE NUMBER (e.g., if "1,000 tons of wheat", `quantity` should be 1000). Extract `price_per_unit` as a PURE NUMBER.
        - Example Keys: `contract_date`, `buyer_name` (e.g., the bank), `seller_name`, `asset_description` (e.g., "wheat"), `quantity` (NUMBER), `price_per_unit` (NUMBER), `total_salam_price` (NUMBER, if explicitly stated as paid, otherwise it will be calculated), `delivery_date`, `currency`.
        - Example Salam Parameter Structure:
          "parameters": {
              "contract_date": "2023-01-01",
              "buyer_name": "Islamic bank",
              "asset_description": "wheat",
              "quantity": 1000,
              "price_per_unit": 300,
              "currency": "USD",
              "delivery_date": "2023-07-01"
          }

        Specific Instructions for Zakat on Business Assets:
        - Extract individual asset and liability values as PURE NUMBERS.
        - Example Keys: `zakat_calculation_date`, `cash_balance`, `accounts_receivable`, `inventory_value`, `fixed_assets_value` (for non-trade assets), `short_term_debts` (or `debts_due_within_a_year`), `currency`.
        - If LLM pre-calculates totals: `current_zakatable_assets_value`, `current_zakatable_liabilities_value`.

        **Specific Instructions for Istisna'a:**
        **- Differentiate between the Istisna'a contract where the bank is the buyer (from a manufacturer) and any Parallel Istisna'a where the bank is the seller (to an end client).**
        **- If a number of items are being produced (e.g., "50 custom desks"), extract this as `quantity` (NUMBER).**
        **- If a cost or price is specified "per item" or "each" along with a quantity, extract the `cost_per_unit` (NUMBER) or `sale_price_per_unit` (NUMBER).**
        **- If a total cost or total sale price is given for all items, extract it as `total_istisnaa_cost` (NUMBER) or `total_sale_price_to_client` (NUMBER).**
        **- The LLM should prioritize extracting per-unit costs/prices and quantity if available. If only totals are available, extract those.**
        **- `number_of_installments_to_manufacturer` should also be a PURE NUMBER.**
        **- Example Keys for Bank as Buyer: `contract_date`, `asset_description`, `quantity` (NUMBER, if applicable), `cost_per_unit` (NUMBER, if applicable), `total_istisnaa_cost` (NUMBER, if quantity/per_unit not applicable or if it's the only cost figure), `manufacturer_name`, `number_of_installments_to_manufacturer` (NUMBER), `delivery_duration_months` (NUMBER), `currency`.**
        **- Example Keys for Bank as Seller (Parallel Istisna'a): `quantity` (NUMBER, should match buyer's quantity if same items), `sale_price_per_unit` (NUMBER, if applicable), `total_sale_price_to_client` (NUMBER, if quantity/per_unit not applicable or only total given), `client_name`.**
        **- Example Istisna'a Parameter Structure (multiple items, per-unit pricing):**
          **"parameters": {**
              **"contract_date": "YYYY-MM-DD",**
              **"bank_name": "Delta Islamic Bank",**
              **"asset_description": "custom desks",**
              **"manufacturer_name": "furniture manufacturer",**
              **"quantity": 50, // "50 custom desks"**
              **"cost_per_unit": 400, // "Cost per desk: USD 400"**
              **"currency": "USD",**
              **// "number_of_installments_to_manufacturer" might be implicit or specified**
              **// "delivery_duration_months" might be implicit or specified**
              **"sale_price_per_unit": 500, // "sell the desks at USD 500 each"**
              **"client_name": "university"**
          **}}**
        **- Example Istisna'a Parameter Structure (single item, total pricing from previous example):**
          **"parameters": {{**
              **"contract_date": "YYYY-MM-DD",**
              **"bank_name": "Omega Islamic Bank",**
              **"asset_description": "custom power generator",**
              **"total_istisnaa_cost": 500000, // "for USD 500,000" (to manufacturer)**
              **"manufacturer_name": "a manufacturer",**
              **"number_of_installments_to_manufacturer": 3,**
              **"delivery_duration_months": 10,**
              **"currency": "USD",**
              **"total_sale_price_to_client": 580000, // "sells the generator to a client at USD 580,000"**
              **"client_name": "a client"**
          **}}**
        """
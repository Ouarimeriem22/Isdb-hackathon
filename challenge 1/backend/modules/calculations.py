import pandas as pd
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import json
import os
import re # For trying to clean up numbers

# --- Load Rules/Narratives ---
RULES_DATA = {}
try:
    # ... (rules loading logic - no change) ...
    rules_path_backend_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules.json")
    rules_path_current_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")

    if os.path.exists(rules_path_backend_root):
        rules_path = rules_path_backend_root
    elif os.path.exists(rules_path_current_dir):
        rules_path = rules_path_current_dir
    else:
        rules_path = None

    if rules_path:
        with open(rules_path, "r", encoding="utf-8") as f:
            RULES_DATA = json.load(f)
        print(f"INFO: (calculations.py) Successfully loaded rules.json from '{rules_path}'")
    else:
        print(f"WARNING: (calculations.py) rules.json not found. Using empty rules. Searched: '{rules_path_backend_root}' and '{rules_path_current_dir}'")
        RULES_DATA = {
            "IjarahMBT": {"InitialRecognition": {}}, 
            "Murabaha": {"InitialRecognition": {}}, 
            "Zakat": {"BusinessAssets": {}}, 
            "Salam": {"ContractImplications": {}}, 
            "Istisnaa": {"ContractImplications": {}}, 
            "General": {}
        }
except Exception as e:
    print(f"WARNING: (calculations.py) Could not load rules.json. Error: {e}. Using empty rules.")
    RULES_DATA = {
        "IjarahMBT": {"InitialRecognition": {}}, 
        "Murabaha": {"InitialRecognition": {}},
        "Zakat": {"BusinessAssets": {}},
        "Salam": {"ContractImplications": {}},
        "Istisnaa": {"ContractImplications": {}},
        "General": {}
    }

# --- Helper Functions ---
def to_decimal(value, default_if_none=Decimal('0')):
    if value is None: return default_if_none
    try:
        if isinstance(value, Decimal): return value
        
        str_value = str(value).strip()
        if not str_value: return default_if_none 

        str_value = re.sub(r"[^\d.\-%]", "", str_value) 

        if not str_value: 
             print(f"WARNING: (to_decimal) Value '{value}' became empty after stripping non-numeric. Returning default.")
             return default_if_none

        if str_value.endswith('%'):
            num_part = str_value[:-1].strip()
            if not num_part: return default_if_none
            if not (num_part.replace('.', '', 1).isdigit() or (num_part.startswith('-') and num_part[1:].replace('.', '', 1).isdigit())):
                print(f"WARNING: (to_decimal) Percentage part '{num_part}' is non-numeric. Returning default.")
                return default_if_none
            return Decimal(num_part) / Decimal('100')
        
        if not (str_value.replace('.', '', 1).isdigit() or (str_value.startswith('-') and str_value[1:].replace('.', '', 1).isdigit())):
            print(f"WARNING: (to_decimal) Cleaned value '{str_value}' (from original '{value}') is still non-numeric. Returning default.")
            return default_if_none
            
        return Decimal(str_value)
    except (InvalidOperation, TypeError, ValueError) as e:
        print(f"WARNING: (to_decimal) Could not convert '{value}' (original type: {type(value)}) to Decimal. Error: {e}. Using default: {default_if_none}")
        return default_if_none

def format_display_amount(d_value: Decimal, add_currency_symbol="USD ", with_commas=True, decimal_places=0):
    if d_value is None: return ""
    if not isinstance(d_value, Decimal):
        d_value = to_decimal(d_value, Decimal('0')) 
    
    if decimal_places == 0:
        quantizer, fmt_str = Decimal('1'), "{:,.0f}" if with_commas else "{:.0f}"
    elif decimal_places == 2:
        quantizer, fmt_str = Decimal('0.01'), "{:,.2f}" if with_commas else "{:.2f}"
    else: 
        quantizer, fmt_str = Decimal('1'), "{:,.0f}" if with_commas else "{:.0f}"
    
    try:
        quantized_value = d_value.quantize(quantizer, ROUND_HALF_UP)
        if quantized_value.is_zero() and quantized_value.is_signed(): 
            quantized_value = Decimal('0')
        formatted_num = fmt_str.format(quantized_value)

    except InvalidOperation: 
        formatted_num = "Error"
        
    return f"{add_currency_symbol}{formatted_num}" if add_currency_symbol and add_currency_symbol.strip() else formatted_num


def format_percentage(d_value: Decimal):
    if d_value is None: return "N/A"
    if not isinstance(d_value, Decimal): d_value = to_decimal(d_value, Decimal('0'))
    return f"{(d_value * Decimal('100')).quantize(Decimal('0.01'), ROUND_HALF_UP)}%"

# --- Ijarah MBT Calculation (Dynamic) ---
# backend/modules/calculations.py
# ... (keep other functions and helpers as they are) ...

# --- Ijarah MBT Calculation (Dynamic) ---
def calculate_ijarah_mbt_initial_recognition(params: dict):
    try:
        print(f"DEBUG: (Ijarah MBT) Received parameters: {params}")
        ijarah_rules = RULES_DATA.get("IjarahMBT", {}).get("InitialRecognition", {})
        general_rules = RULES_DATA.get("General", {})

        # --- Parameter Extraction with more robust key searching for components ---
        cost_components_raw = params.get("asset_initial_cost_components", [])
        
        purchase_price = Decimal(0)
        import_duty_val = Decimal(0)
        freight_charges_val = Decimal(0) # Covers freight
        registration_fees_val = Decimal(0) # Covers registration
        other_direct_costs_val = Decimal(0) # A general bucket for other direct costs

        if cost_components_raw and isinstance(cost_components_raw, list):
            for comp in cost_components_raw:
                if isinstance(comp, dict):
                    val = to_decimal(comp.get("value"), Decimal('0'))
                    comp_type = str(comp.get("type", "")).lower().replace("_", "").replace(" ", "")
                    
                    if "purchaseprice" in comp_type: 
                        purchase_price = val
                    elif "importduty" in comp_type or "importtax" in comp_type: 
                        import_duty_val = val
                    elif "freightcharges" in comp_type or "freight" in comp_type: # Broader match for freight
                        freight_charges_val += val # Accumulate if multiple freight entries
                    elif "registrationfees" in comp_type or "registration" in comp_type: # Broader match for registration
                        registration_fees_val += val
                    elif "otherdirectcosts" in comp_type or "installation" in comp_type : # Example for other costs
                        other_direct_costs_val += val
        
        # Fallback if LLM gives a single total_asset_cost (less ideal for your desired method)
        # or if the specific "Freight and registration" was a single value not in components
        asset_cost_param = params.get("asset_cost") # Example: "Asset cost: USD 250,000"
        if purchase_price == 0 and asset_cost_param is not None:
            purchase_price = to_decimal(asset_cost_param)
            print("INFO: (Ijarah MBT) Used 'asset_cost' as purchase_price.")

        # Check for combined freight/registration if not itemized by LLM
        freight_and_registration_combined = params.get("freight_and_registration")
        if freight_charges_val == 0 and registration_fees_val == 0 and freight_and_registration_combined is not None:
            # This is a fallback if LLM sends a single key for combined costs
            # We'll put it into freight_charges_val for simplicity in the sum
            freight_charges_val = to_decimal(freight_and_registration_combined)
            print(f"INFO: (Ijarah MBT) Used 'freight_and_registration' value: {freight_charges_val}")


        # --- Values from params ---
        lease_term_years = to_decimal(params.get("lease_term_years") or params.get("ijarah_term_years"))
        yearly_rental = to_decimal(params.get("annual_rental") or params.get("yearly_rental"))
        option_price = to_decimal(params.get("purchase_option_at_end") or params.get("ownership_transfer_option_price"))
        # Expected residual value (as per your model output, but not your desired solution's calculation for ROU)
        expected_rv_at_lease_end = to_decimal(params.get("expected_residual_value_at_lease_end"), default_if_none=Decimal('0')) 
        commencement_date_str = str(params.get("commencement_date", "Not Specified"))
        currency_symbol_param = str(params.get("currency", "USD"))
        currency_display = f"{currency_symbol_param} " if currency_symbol_param and currency_symbol_param.strip() else ""

        # --- Validations (basic) ---
        if purchase_price <= 0 : 
            # Try total_asset_cost if purchase_price from components is zero
            total_asset_cost_fallback = to_decimal(params.get("total_asset_cost"))
            if total_asset_cost_fallback > 0:
                purchase_price = total_asset_cost_fallback
                print(f"WARNING: (Ijarah MBT) Used 'total_asset_cost' ({purchase_price}) as purchase_price because component breakdown was zero.")
            else:
                return None, "Purchase price or total asset cost for Ijarah MBT must be positive."
        if lease_term_years <= 0 : return None, "Lease term for Ijarah MBT must be positive."
        if yearly_rental <= 0 : return None, "Yearly rental for Ijarah MBT must be positive."
        if option_price < 0 : return None, "Purchase option price cannot be negative." # Allow 0 for nominal

        # --- Calculations (as per YOUR DESIRED Ijarah solution) ---
        prime_cost = purchase_price + import_duty_val + freight_charges_val + registration_fees_val + other_direct_costs_val
        
        # ROU Asset as per your solution: Prime Cost - Purchase Option
        rou_asset_value = prime_cost - option_price
        if rou_asset_value < 0: # Should not happen in a typical scenario
            print(f"WARNING: (Ijarah MBT) ROU Asset value calculated as negative ({rou_asset_value}). This might indicate issues with input values (e.g., option price > prime cost). Setting ROU to 0.")
            rou_asset_value = Decimal('0')

        # Liability as per your solution: Total Rentals
        total_rentals_payable = yearly_rental * lease_term_years
        ijarah_liability_value = total_rentals_payable
        
        # Deferred Ijarah Cost as per your solution
        deferred_ijarah_cost_value = ijarah_liability_value - rou_asset_value
        # If deferred cost is negative (ROU > Liability), this usually means underlying economics are unusual or
        # this simplified accounting method has limitations. For AAOIFI, often finance charge cannot be negative.
        if deferred_ijarah_cost_value < 0:
            print(f"WARNING: (Ijarah MBT) Deferred Ijarah Cost is negative ({deferred_ijarah_cost_value}). This method might not fully capture complex scenarios. Setting to 0 for presentation.")
            deferred_ijarah_cost_value = Decimal('0')


        # Amortizable Amount Calculation for ROU Asset (still based on ROU asset and its *actual* residual value)
        # Your desired solution doesn't explicitly show amortization calc, but it's good practice.
        # The ROU asset calculated (prime_cost - option_price) will be amortized.
        # Its "residual value" for amortization purposes would be 0 if it's transferred for the option price.
        # Or, if `expected_residual_value_at_lease_end` is different from `option_price` AND ownership is certain,
        # then the asset is typically amortized down to the `option_price` if that's its effective salvage.
        # However, your model's ROU asset is already net of the option price.
        # So, we amortize this ROU asset. If there's a *further* residual value beyond the option price (unlikely if transfer is certain),
        # then the amortization base would be ROU - (expected_rv - option_price), but this gets complex.
        # Simpler: Amortize the ROU (prime_cost - option_price) over the lease term.
        # If `expected_rv_at_lease_end` from params is > 0, it means the asset has value at end, but lessee gets it for `option_price`.
        # The ROU of `prime_cost - option_price` already accounts for the benefit of getting it at `option_price`.
        # So, amortizable amount for THIS ROU is `rou_asset_value` itself, assuming it will be nil after transfer.
        # OR, if we use the `expected_rv_at_lease_end` *in relation to the prime_cost*:
        # Amortizable amount (for prime_cost) = prime_cost - expected_rv_at_lease_end (if using prime_cost as depreciable base)
        # But your ROU is different. Let's stick to amortizing the ROU you calculated.
        # If the ROU (prime_cost - option_price) is considered the value lessee obtains, and at the end they own it,
        # it's amortized fully unless there's a residual value to *the lessee* after they acquire it for the option price.
        # For your model, ROU = 260,000. If we assume this is the useful value consumed, amortize 260,000.
        
        amortizable_amount_for_rou = rou_asset_value # Amortize the calculated ROU asset
        # The amortization note about `expected_residual_value_at_lease_end` might be confusing now.
        # Let's keep it but clarify its context if it's not 0.


        # --- Build Structured Output ---
        output_structure = {
            "title": f"Ijarah MBT: Initial Recognition ({commencement_date_str}) - Custom Method",
            "sub_title": ijarah_rules.get("ROU_CalculationNote_Custom", "ROU Asset determined by Prime Cost less Purchase Option Price."),
            "sections": [
                {
                    "type": "calculation_block", "heading": "1. Determine Prime Cost of Asset",
                    "steps": [
                        {"label": "Asset Cost / Purchase Price", "result_value": float(purchase_price), "result_display": format_display_amount(purchase_price, currency_display, True)},
                        {"label": "Add: Import Duty", "result_value": float(import_duty_val), "result_display": format_display_amount(import_duty_val, currency_display, True)},
                        {"label": "Add: Freight Charges", "result_value": float(freight_charges_val), "result_display": format_display_amount(freight_charges_val, currency_display, True)},
                        {"label": "Add: Registration Fees", "result_value": float(registration_fees_val), "result_display": format_display_amount(registration_fees_val, currency_display, True)},
                        {"label": "Add: Other Direct Costs", "result_value": float(other_direct_costs_val), "result_display": format_display_amount(other_direct_costs_val, currency_display, True)},
                        {"label": "Total Prime Cost",
                         "calculation_display": f"Sum of above costs",
                         "result_value": float(prime_cost), "result_display": f"{format_display_amount(prime_cost, currency_display, True)}"}
                    ]
                },
                {
                    "type": "calculation_block", "heading": "2. Determine Right-of-Use (ROU) Asset",
                    "steps": [
                        {"label": "Prime Cost (as calculated above)", "result_value": float(prime_cost), "result_display": format_display_amount(prime_cost, currency_display, True)},
                        {"label": f"Less: Terminal Value (Purchase Option Price)", "result_value": float(option_price), "result_display": format_display_amount(option_price, currency_display, True)},
                        {"label": "Right-of-Use (ROU) Asset",
                         "calculation_display": f"{format_display_amount(prime_cost, '', False)} - {format_display_amount(option_price, '', False)}",
                         "result_value": float(rou_asset_value), "result_display": format_display_amount(rou_asset_value, currency_display, True)}
                    ]
                },
                {
                    "type": "calculation_block", "heading": "3. Determine Ijarah Liability & Deferred Ijarah Cost",
                    "steps": [
                        {"label": f"Total Rentals over {lease_term_years} years (Ijarah Liability)",
                         "calculation_display": f"{format_display_amount(yearly_rental, '', True)} × {lease_term_years}",
                         "result_value": float(total_rentals_payable), "result_display": format_display_amount(total_rentals_payable, currency_display, True)},
                        {"label": "Less: Value of ROU Asset (as calculated above)",
                         "result_value": float(rou_asset_value), "result_display": format_display_amount(rou_asset_value, currency_display, True)},
                        {"label": "Deferred Ijarah Cost",
                         "calculation_display": f"{format_display_amount(total_rentals_payable, '', False)} - {format_display_amount(rou_asset_value, '', False)}",
                         "result_value": float(deferred_ijarah_cost_value), "result_display": format_display_amount(deferred_ijarah_cost_value, currency_display, True)}
                    ]
                },
                {
                    "type": "journal_entry", "heading": "4. Journal Entry at Commencement:",
                    "entries": [
                        {"account": "Dr. Right of Use Asset (ROU)", "amount_display": format_display_amount(rou_asset_value, currency_display), "debit": float(rou_asset_value), "credit": 0},
                        {"account": "Dr. Deferred Ijarah Cost", "amount_display": format_display_amount(deferred_ijarah_cost_value, currency_display), "debit": float(deferred_ijarah_cost_value), "credit": 0},
                        {"account": "Cr. Ijarah Liability", "amount_display": format_display_amount(ijarah_liability_value, currency_display), "debit": 0, "credit": float(ijarah_liability_value)}
                    ]
                },
                { # Amortization part might need re-thinking based on this new ROU
                    "type": "calculation_table", "heading": "5. Amortizable Amount Calculation (for ROU Asset)",
                    "description_column_header": "Description", "value_column_header": currency_symbol_param,
                    "rows": [
                        {"description": "Cost of ROU Asset (Prime Cost - Purchase Option)", "value_display": format_display_amount(rou_asset_value, '')},
                        # If expected_rv_at_lease_end represents the value of the asset after the lessee has acquired it for the option_price,
                        # then this could be a salvage value for the ROU asset.
                        # However, the ROU already reflects the benefit of the cheap purchase.
                        # If expected_rv_at_lease_end from parameters is, say, 12,000 and option is 10,000
                        # it means lessee gets an asset worth 12k for 10k. The ROU is (Prime Cost - 10k).
                        # This ROU will be used up over the lease term.
                        {"description": "Less: Salvage Value (if any, for the ROU asset after acquisition)", "value_display": format_display_amount(Decimal('0'), '')}, # Assuming ROU is fully amortized
                        {"description": "Amortizable Amount", "value_display": format_display_amount(amortizable_amount_for_rou, '')}
                    ],
                    "footer_note": ijarah_rules.get("AmortizableAmount_Footer_Custom", 
                        f"This ROU asset value of {format_display_amount(rou_asset_value, currency_display, True)} will typically be amortized over the lease term of {lease_term_years} years. The `expected_residual_value_at_lease_end` of {format_display_amount(expected_rv_at_lease_end, currency_display,True)} relates to the underlying asset's value, which the lessee acquires for the option price of {format_display_amount(option_price, currency_display, True)}.")
                }
            ],
            "disclaimer": general_rules.get("CalculationDisclaimer", "Please consult official AAOIFI standards for definitive guidance. This custom calculation method may differ from standard IFRS 16.")
        }
        print(f"DEBUG: (Ijarah MBT) Successfully generated output structure using custom method.")
        return output_structure, None

    except Exception as e:
        error_msg = f"Unexpected error in Ijarah MBT detailed calculation: {str(e)}"
        print(f"ERROR: (Ijarah MBT) {error_msg}")
        import traceback; traceback.print_exc()
        return None, error_msg

# ... (Keep Murabaha, Zakat, Salam, Istisnaa functions as they are from previous full version) ...

    except Exception as e:
        error_msg = f"Unexpected error in Ijarah MBT detailed calculation: {str(e)}"
        print(f"ERROR: (Ijarah MBT) {error_msg}")
        import traceback; traceback.print_exc()
        return None, error_msg

# --- Murabaha Calculation ---
def calculate_murabaha_from_params(params: dict):
    # ... (Murabaha code - no changes) ...
    try:
        print(f"DEBUG: (Murabaha) Received parameters: {params}")
        murabaha_rules = RULES_DATA.get("Murabaha", {}).get("InitialRecognition", {})
        general_rules = RULES_DATA.get("General", {})
        transaction_date_str = str(params.get("contract_date") or params.get("transaction_date", "Not Specified"))

        potential_cost_keys = [
            "asset_cost_to_seller", "asset_cost_to_bank", "cost_price",
            "original_asset_cost", "purchase_cost_of_asset", "asset_purchase_price_for_seller",
            "cost_of_goods_for_seller", "seller_cost", "asset_cost_to_financier"
        ]
        asset_cost_to_seller = Decimal('0')
        found_cost_key = None
        for key in potential_cost_keys:
            cost_val = params.get(key)
            if cost_val is not None:
                if isinstance(cost_val, str) and not cost_val.strip():
                    print(f"WARNING: (Murabaha) Empty string value for cost key '{key}'. Skipping.")
                    continue
                parsed_cost = to_decimal(cost_val)
                if parsed_cost > 0:
                    asset_cost_to_seller = parsed_cost
                    found_cost_key = key
                    print(f"INFO: (Murabaha) asset_cost_to_seller found using key '{found_cost_key}': {asset_cost_to_seller}")
                    break
        
        profit_margin_percentage_param = params.get("profit_margin_percentage")
        profit_amount_fixed_param = params.get("profit_amount_fixed")
        sale_price_to_customer_param = params.get("sale_price_to_customer") or \
                                       params.get("agreed_selling_price_to_client") or \
                                       params.get("selling_price")

        number_of_installments = to_decimal(params.get("number_of_installments"), default_if_none=Decimal('0'))
        down_payment_amount = to_decimal(params.get("down_payment_amount"), default_if_none=Decimal('0'))
        
        if asset_cost_to_seller <= 0:
            error_msg = "Asset cost to seller/bank for Murabaha must be positive and was not found or provided correctly."
            print(f"ERROR: (Murabaha) {error_msg}. Searched keys: {potential_cost_keys}. Params: {params}")
            return None, error_msg

        total_profit = Decimal('0')
        calculated_sale_price = Decimal('0')
        profit_calculation_method_desc = ""

        if sale_price_to_customer_param is not None:
            parsed_sale_price = to_decimal(sale_price_to_customer_param)
            if parsed_sale_price == Decimal('0') and sale_price_to_customer_param is not None : 
                 print(f"WARNING: (Murabaha) sale price provided as {parsed_sale_price}.")
            calculated_sale_price = parsed_sale_price 
            if calculated_sale_price <= asset_cost_to_seller:
                print(f"WARNING: (Murabaha) sale price ({calculated_sale_price}) is not greater than cost ({asset_cost_to_seller}).")
            total_profit = calculated_sale_price - asset_cost_to_seller
            profit_calculation_method_desc = f"Based on provided Sale Price ({format_display_amount(calculated_sale_price, '', False)}) and Cost ({format_display_amount(asset_cost_to_seller, '', False)})"

        elif profit_margin_percentage_param is not None:
            profit_margin_percentage_decimal = to_decimal(profit_margin_percentage_param)
            total_profit = asset_cost_to_seller * profit_margin_percentage_decimal
            calculated_sale_price = asset_cost_to_seller + total_profit
            profit_calculation_method_desc = f"Based on Profit Margin ({format_percentage(profit_margin_percentage_decimal)} of Cost)"
        elif profit_amount_fixed_param is not None:
            total_profit = to_decimal(profit_amount_fixed_param)
            calculated_sale_price = asset_cost_to_seller + total_profit
            profit_calculation_method_desc = f"Based on Fixed Profit Amount ({format_display_amount(total_profit, '', False)})"
        else:
            return None, "Murabaha profit information (margin, fixed amount, or sale price) is missing."
        
        if total_profit < 0 :
            print(f"WARNING: (Murabaha) total profit is negative ({total_profit}). This indicates a sale at a loss.")

        murabaha_receivable_gross = calculated_sale_price - down_payment_amount
        is_installment_sale = number_of_installments > 0 and number_of_installments.is_finite() and int(number_of_installments) > 0
        installment_amount = Decimal('0')
        profit_per_installment = Decimal('0')

        if is_installment_sale:
            if murabaha_receivable_gross != 0: 
                installment_amount = (murabaha_receivable_gross / number_of_installments).quantize(Decimal('0.01'), ROUND_HALF_UP)
            
            profit_in_receivable = total_profit 
            if calculated_sale_price != 0 and murabaha_receivable_gross != calculated_sale_price : 
                 profit_in_receivable = total_profit * (murabaha_receivable_gross / calculated_sale_price) if calculated_sale_price > 0 else Decimal(0)
            elif calculated_sale_price == 0 and murabaha_receivable_gross == 0 :
                 profit_in_receivable = Decimal(0)

            if number_of_installments > 0 and profit_in_receivable != 0:
                 profit_per_installment = (profit_in_receivable / number_of_installments).quantize(Decimal('0.01'), ROUND_HALF_UP)

        output_structure = {
            "title": f"Murabaha: Initial Recognition of Sale ({transaction_date_str})",
            "sub_title": murabaha_rules.get("SaleRecognitionNote", "Recognition of Murabaha sale and related receivable."),
            "sections": [
                {
                    "type": "calculation_block", "heading": "1. Determine Murabaha Sale Price and Profit",
                    "steps": [
                        {"label": "Cost of Asset to Seller/Bank", "result_value": float(asset_cost_to_seller), "result_display": format_display_amount(asset_cost_to_seller, '', True)},
                        {"label": f"Total Profit ({profit_calculation_method_desc})",
                         "calculation_display": (f"{format_display_amount(asset_cost_to_seller, '', False)} × {format_percentage(to_decimal(profit_margin_percentage_param))}" if profit_margin_percentage_param is not None and sale_price_to_customer_param is None else \
                                                f"{format_display_amount(calculated_sale_price, '', False)} - {format_display_amount(asset_cost_to_seller, '', False)}" if sale_price_to_customer_param is not None else \
                                                f"Fixed Amount" if profit_amount_fixed_param is not None else ""),
                         "result_value": float(total_profit), "result_display": format_display_amount(total_profit, '', True)},
                        {"label": "Murabaha Selling Price to Customer", "calculation_display": f"{format_display_amount(asset_cost_to_seller, '', False)} + {format_display_amount(total_profit, '', False)}",
                         "result_value": float(calculated_sale_price), "result_display": format_display_amount(calculated_sale_price, '', True)}
                    ]
                }
            ]
        }

        if down_payment_amount > 0:
            output_structure["sections"].append({
                "type": "calculation_block", "heading": "2. Account for Down Payment",
                "steps": [
                    {"label": "Murabaha Selling Price", "result_value": float(calculated_sale_price), "result_display": format_display_amount(calculated_sale_price, '', True)},
                    {"label": "Less: Down Payment Received", "result_value": float(down_payment_amount), "result_display": format_display_amount(down_payment_amount, '', True)},
                    {"label": "Net Murabaha Receivable (Deferred Amount)", "calculation_display": f"{format_display_amount(calculated_sale_price, '', False)} - {format_display_amount(down_payment_amount, '', False)}",
                     "result_value": float(murabaha_receivable_gross), "result_display": format_display_amount(murabaha_receivable_gross, '', True)}
                ]
            })
        
        next_section_number = 3 if down_payment_amount > 0 else 2

        if is_installment_sale:
            output_structure["sections"].append({
                "type": "calculation_block", "heading": f"{next_section_number}. Installment Details (for Deferred Amount)",
                "steps": [
                    {"label": "Number of Installments", "result_value": float(number_of_installments), "result_display": str(int(number_of_installments))},
                    {"label": "Amount per Installment (approx.)",
                     "calculation_display": f"{format_display_amount(murabaha_receivable_gross, '', False, decimal_places=2)} / {int(number_of_installments)}" if number_of_installments > 0 else "N/A",
                     "result_value": float(installment_amount), "result_display": format_display_amount(installment_amount, '', True, decimal_places=2)},
                    {"label": "Profit Portion per Installment (approx.)",
                     "calculation_display": f"{format_display_amount(profit_in_receivable, '', False, decimal_places=2)} / {int(number_of_installments)}" if number_of_installments > 0 else "N/A",
                     "result_value": float(profit_per_installment), "result_display": format_display_amount(profit_per_installment, '', True, decimal_places=2)}
                ]
            })
            next_section_number +=1

        journal_entries = []
        if down_payment_amount > 0:
            journal_entries.append({"account": "Dr. Cash / Bank (Down Payment)", "amount_display": format_display_amount(down_payment_amount), "debit": float(down_payment_amount), "credit": 0})
        
        if murabaha_receivable_gross != 0 : 
            journal_entries.append({"account": "Dr. Murabaha Receivable", "amount_display": format_display_amount(murabaha_receivable_gross), "debit": float(murabaha_receivable_gross), "credit": 0})
        
        journal_entries.append({"account": "Cr. Asset / Inventory Sold", "amount_display": format_display_amount(asset_cost_to_seller), "debit": 0, "credit": float(asset_cost_to_seller)})

        if total_profit > 0:
            journal_entries.append({"account": "Cr. Deferred Murabaha Income/Profit", "amount_display": format_display_amount(total_profit), "debit": 0, "credit": float(total_profit)})
        elif total_profit < 0:
             journal_entries.append({"account": "Dr. Loss on Murabaha Sale", "amount_display": format_display_amount(abs(total_profit)), "debit": float(abs(total_profit)), "credit": 0})

        output_structure["sections"].append({
            "type": "journal_entry", "heading": f"{next_section_number}. Journal Entry at Time of Sale:", "entries": journal_entries,
            "narrative_below_entries": murabaha_rules.get("JournalEntryNote", "This entry records the sale...")
        })
        output_structure["disclaimer"] = general_rules.get("CalculationDisclaimer", "Please consult official AAOIFI/IFRS standards...")
        
        print(f"DEBUG: (Murabaha) Successfully generated output structure.")
        return output_structure, None

    except Exception as e:
        error_msg = f"Unexpected error in Murabaha detailed calculation: {str(e)}"
        print(f"ERROR: (Murabaha) {error_msg}")
        import traceback; traceback.print_exc()
        return None, error_msg

# --- Zakat Calculation for Business Assets ---
# backend/modules/calculations.py
# ... (Keep other functions: Ijarah, Murabaha, Salam, Istisnaa, and helpers as they are) ...

# --- Zakat Calculation for Business Assets ---
def calculate_zakat_on_business_assets(params: dict):
    try:
        print(f"DEBUG: (Zakat BA) Received parameters for Zakat calc: {params}") 
        
        zakat_rules = RULES_DATA.get("Zakat", {}).get("BusinessAssets", {})
        general_rules = RULES_DATA.get("General", {})
        
        # --- Parameter Extraction ---
        potential_date_keys = ["zakat_calculation_date", "zakat_date", "date_of_calculation", "assessment_date", "on_date"]
        zakat_date_str = "Not Specified"
        for key in potential_date_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): zakat_date_str = str(val); break
            
        currency_symbol = str(params.get("currency", "USD")) 
        currency_display_for_format_amount = f"{currency_symbol} " if currency_symbol else ""

        # --- Initialize variables ---
        cash_balance = Decimal('0')
        accounts_receivable = Decimal('0')
        inventory_value = Decimal('0')
        gold_value = Decimal('0') # <<< ADDED GOLD
        # silver_value = Decimal('0') # For future expansion
        # trade_investments_value = Decimal('0') # For future expansion

        total_zakatable_assets_individual_components = Decimal('0')
        short_term_debts_individual_components = Decimal('0')
        fixed_assets_value = Decimal('0') # For informational note

        # --- Check for pre-calculated totals first ---
        total_zakatable_assets = to_decimal(params.get("current_zakatable_assets_value") or \
                                            params.get("total_zakatable_assets") or \
                                            params.get("zakatable_assets_total"))
        
        short_term_debts = to_decimal(params.get("current_zakatable_liabilities_value") or \
                                      params.get("total_zakatable_liabilities") or \
                                      params.get("short_term_debts_total") or \
                                      params.get("deductible_liabilities"))

        display_individual_components = False # Flag to control output sections

        if total_zakatable_assets > 0 or (total_zakatable_assets == 0 and "current_zakatable_assets_value" in params): 
            print("INFO: (Zakat BA) Using pre-calculated total_zakatable_assets from LLM.")
            # If using pre-calculated, we might still want to show gold if LLM sent it separately for transparency
            potential_gold_keys_for_display = ["gold_value", "gold", "value_of_gold"]
            for key in potential_gold_keys_for_display:
                val = params.get(key)
                if val is not None: gold_value = to_decimal(val); break # Store it even if not used in sum
        else:
            print("INFO: (Zakat BA) Pre-calculated total_zakatable_assets not found or zero. Attempting to sum individual components.")
            display_individual_components = True 

            potential_cash_keys = ["cash_balance", "cash", "cash_on_hand", "cash_in_bank"]
            potential_ar_keys = ["accounts_receivable", "receivables", "trade_debtors"]
            potential_inventory_keys = ["inventory_value", "inventory", "stock_value", "merchandise_inventory"]
            potential_gold_keys = ["gold_value", "gold", "value_of_gold"] # <<< ADDED GOLD KEYS
            
            for key in potential_cash_keys:
                val = params.get(key)
                if val is not None: cash_balance = to_decimal(val); break
            
            for key in potential_ar_keys:
                val = params.get(key)
                if val is not None: accounts_receivable = to_decimal(val); break

            for key in potential_inventory_keys:
                val = params.get(key)
                if val is not None: inventory_value = to_decimal(val); break
            
            for key in potential_gold_keys: # <<< ADDED GOLD EXTRACTION
                val = params.get(key)
                if val is not None: gold_value = to_decimal(val); break
            
            total_zakatable_assets_individual_components = cash_balance + accounts_receivable + inventory_value + gold_value # <<< ADDED GOLD TO SUM
            total_zakatable_assets = total_zakatable_assets_individual_components

            # Also try to get individual short-term debts if pre-calculated total was not used
            if not (short_term_debts > 0 or (short_term_debts == 0 and "current_zakatable_liabilities_value" in params)):
                potential_short_term_debt_keys = [
                    "short_term_debts", "debts_due_within_one_year", "debts_due_within_a_year", 
                    "current_liabilities_for_zakat", "short_term_liabilities", "current_debts"
                ]
                for key in potential_short_term_debt_keys:
                    val = params.get(key)
                    if val is not None: short_term_debts_individual_components = to_decimal(val); break
                short_term_debts = short_term_debts_individual_components


        # Extract fixed_assets_value for informational note regardless
        potential_fixed_assets_keys = ["fixed_assets_value", "fixed_assets", "property_plant_equipment", "fixed_assets_non_trade"]
        for key in potential_fixed_assets_keys:
            val = params.get(key)
            if val is not None: fixed_assets_value = to_decimal(val); break

        # --- Calculations ---
        net_zakatable_assets_before_adjustment = total_zakatable_assets - short_term_debts
        net_zakatable_assets = max(Decimal('0'), net_zakatable_assets_before_adjustment)

        zakat_rate = Decimal("0.025") 
        potential_zakat_due = net_zakatable_assets * zakat_rate
        
        # --- Build Structured Output ---
        output_structure = {
            "title": f"Zakat Calculation on Assets ({zakat_date_str})", # Made title more generic
            "sub_title": zakat_rules.get("CalculationIntro", "Calculation of the Zakat base for relevant assets."),
            "sections": []
        }

        if display_individual_components:
            zakatable_asset_rows = [
                {"description": "Cash Balance", "value_display": format_display_amount(cash_balance, currency_display_for_format_amount, True)},
                {"description": "Accounts Receivable (Likely to be collected)", "value_display": format_display_amount(accounts_receivable, currency_display_for_format_amount, True)},
                {"description": "Inventory (Current Value)", "value_display": format_display_amount(inventory_value, currency_display_for_format_amount, True)},
            ]
            if gold_value > 0: # <<< ADD GOLD TO DISPLAY IF PRESENT
                zakatable_asset_rows.append(
                    {"description": "Gold (Current Value)", "value_display": format_display_amount(gold_value, currency_display_for_format_amount, True)}
                )
            # Add silver, investments etc. here if expanded in future

            output_structure["sections"].append({
                "type": "calculation_table", 
                "heading": "1. Determine Total Zakatable Assets (from individual components)",
                "description_column_header": "Asset Type", "value_column_header": currency_symbol.strip(),
                "rows": zakatable_asset_rows,
                "footer_row": {
                    "description": "Total Zakatable Assets (from components)", "value_display": format_display_amount(total_zakatable_assets, currency_display_for_format_amount, True)
                }
            })
        else: # LLM provided totals or it's a simpler Zakat calculation (e.g. just cash and gold)
             output_structure["sections"].append({
                "type": "calculation_block", 
                "heading": "1. Zakatable Assets and Liabilities (as provided/calculated)",
                "steps": [
                    {"label": "Total Current Zakatable Assets",
                     "result_value": float(total_zakatable_assets), "result_display": format_display_amount(total_zakatable_assets, currency_display_for_format_amount, True)},
                    # Optionally, if gold was extracted separately even with totals, mention it:
                    # {"label": "Including Gold Value (if specified separately)", "result_value": float(gold_value), "result_display": format_display_amount(gold_value, currency_display_for_format_amount, True)} if gold_value > 0 and not display_individual_components else None,
                    {"label": "Total Current Zakatable Liabilities (Short-Term Debts)",
                     "result_value": float(short_term_debts), "result_display": format_display_amount(short_term_debts, currency_display_for_format_amount, True)},
                ]
            })
             # Remove None steps
            # if not display_individual_components:
            #    output_structure["sections"][-1]["steps"] = [s for s in output_structure["sections"][-1]["steps"] if s is not None]


        output_structure["sections"].append({
            "type": "calculation_block", 
            "heading": "2. Determine Net Zakatable Assets (Zakat Base/Pool)",
            "steps": [
                {"label": "Total Zakatable Assets", 
                 "result_value": float(total_zakatable_assets), "result_display": format_display_amount(total_zakatable_assets, currency_display_for_format_amount, True)},
                {"label": "Less: Short-term Debts", 
                 "result_value": float(short_term_debts), "result_display": format_display_amount(short_term_debts, currency_display_for_format_amount, True)},
                {"label": "Net Zakatable Assets (Zakat Base)",
                 "calculation_display": f"{format_display_amount(total_zakatable_assets, '', False)} - {format_display_amount(short_term_debts, '', False)}",
                 "result_value": float(net_zakatable_assets), "result_display": format_display_amount(net_zakatable_assets, currency_display_for_format_amount, True)}
            ]
        })
        
        output_structure["sections"].append({
            "type": "calculation_block",
            "heading": "3. Zakat Payable Calculation",
            "narrative_above_steps": zakat_rules.get("NisabHawlNote", 
                f"If the Net Zakatable Assets exceed the Nisab threshold and the Hawl (one lunar year) condition is met, Zakat is typically {format_percentage(zakat_rate)} of this amount. This calculation shows the Zakat payable if these conditions are met."),
            "steps": [
                 {"label": "Net Zakatable Assets (Zakat Base)",
                 "result_value": float(net_zakatable_assets), "result_display": format_display_amount(net_zakatable_assets, currency_display_for_format_amount, True)},
                 {"label": f"Zakat Rate", "result_value": float(zakat_rate), "result_display": format_percentage(zakat_rate)},
                 {"label": "Zakat Payable",
                 "calculation_display": f"{format_display_amount(net_zakatable_assets, '', False)} × {format_percentage(zakat_rate)}",
                 "result_value": float(potential_zakat_due), "result_display": format_display_amount(potential_zakat_due, currency_display_for_format_amount, True, decimal_places=2)}
            ]
        })
        
        if fixed_assets_value > 0:
             output_structure["sections"].append({
                 "type": "information_block",
                 "heading": "Note on Non-Zakatable Assets",
                 "content": zakat_rules.get("FixedAssetsNote", 
                    f"Fixed Assets (e.g., buildings, machinery used in operations) amounting to {format_display_amount(fixed_assets_value, currency_display_for_format_amount, True)} are generally not subject to Zakat for their capital value in this calculation. Their income, if any, would be part of cash or other Zakatable assets if it meets Hawl and Nisab. This value was extracted as {format_display_amount(fixed_assets_value, currency_display_for_format_amount, True)} but not used in Zakat base calculation directly.")
             }) # Updated note
        
        nisab_value = to_decimal(params.get("nisab_threshold_value") or params.get("nisab_value") or params.get("nisab"))
        if nisab_value > 0 :
            nisab_note = f"The Nisab threshold was identified as {format_display_amount(nisab_value, currency_display_for_format_amount, True)}. Zakat is due if Net Zakatable Assets ({format_display_amount(net_zakatable_assets, currency_display_for_format_amount, True)}) exceed this and Hawl is met."
            if net_zakatable_assets > nisab_value:
                nisab_note += " In this case, the Zakat base exceeds the Nisab."
            else:
                nisab_note += " In this case, the Zakat base does NOT exceed the Nisab, so Zakat may not be due."
            
            output_structure["sections"].append({
                 "type": "information_block",
                 "heading": "Note on Nisab",
                 "content": nisab_note
             })

        output_structure["disclaimer"] = general_rules.get("CalculationDisclaimer", "Please consult official AAOIFI standards or a qualified Zakat scholar for definitive guidance. Nisab value and Hawl conditions must be confirmed.")
        
        print(f"DEBUG: (Zakat BA) Successfully generated Zakat output structure.")
        return output_structure, None

    except Exception as e:
        error_msg = f"Unexpected error in Zakat on Business Assets calculation: {str(e)}"
        print(f"ERROR: (Zakat BA) {error_msg}") 
        import traceback; traceback.print_exc()
        return None, error_msg

# ... (Rest of the functions: Salam, Istisnaa, Zakat on cash savings stub) ...

    except Exception as e:
        error_msg = f"Unexpected error in Zakat on Business Assets calculation: {str(e)}"
        print(f"ERROR: (Zakat BA) {error_msg}") 
        import traceback; traceback.print_exc()
        return None, error_msg

# --- Salam Contract Implications ---
def calculate_salam_transaction_implications(params: dict):
    # ... (Salam code - no changes from previous version) ...
    try:
        print(f"DEBUG: (Salam) Received parameters: {params}")
        salam_rules = RULES_DATA.get("Salam", {}).get("ContractImplications", {})
        general_rules = RULES_DATA.get("General", {})

        potential_contract_date_keys = ["contract_date", "salam_contract_date", "agreement_date", "date_of_salam", "transaction_date"]
        potential_delivery_date_keys = ["delivery_date", "expected_delivery_date", "goods_delivery_date"]
        potential_asset_desc_keys = ["asset_description", "commodity_description", "goods_description", "salam_item", "item_description", "commodity", "product_description"]
        potential_quantity_keys = ["quantity", "salam_quantity", "amount_of_goods", "total_quantity", "contract_quantity", "salam_amount", "number_of_units", "qty", "tons_of_wheat"] 
        potential_price_keys = ["price_per_unit", "salam_price_per_unit", "unit_price", "price_pu", "salam_unit_price", "cost_per_unit", "price_per_ton"] 
        potential_currency_keys = ["currency", "currency_code", "ccy"]

        contract_date = "Not Specified"
        for key in potential_contract_date_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): contract_date = str(val); break
        
        delivery_date = "Not Specified"
        for key in potential_delivery_date_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): delivery_date = str(val); break

        asset_description = "Not Specified"
        for key in potential_asset_desc_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): asset_description = str(val); break
        
        quantity = Decimal('0')
        quantity_found_key_name = None
        print(f"INFO: (Salam) Attempting to parse quantity. Potential keys: {potential_quantity_keys}")
        for key_idx, key_name in enumerate(potential_quantity_keys):
            raw_val = params.get(key_name)
            print(f"INFO: (Salam) Checking quantity key '{key_name}': Raw value is '{raw_val}' (type: {type(raw_val)})")
            if raw_val is not None: 
                parsed_decimal_val = to_decimal(raw_val) 
                print(f"INFO: (Salam) Key '{key_name}' raw value '{raw_val}' parsed to Decimal: {parsed_decimal_val}")
                if parsed_decimal_val > 0 : 
                    quantity = parsed_decimal_val
                    quantity_found_key_name = key_name
                    print(f"INFO: (Salam) VALID quantity found using key '{quantity_found_key_name}': {quantity}")
                    break 
                else:
                    print(f"INFO: (Salam) Quantity key '{key_name}' parsed to {parsed_decimal_val}. Checking next key.")
            if quantity > 0 : break 
        
        if quantity <= 0 and quantity_found_key_name is None: 
             print(f"WARNING: (Salam) After checking all potential keys, no valid positive quantity was parsed. Quantity remains {quantity}.")


        price_per_unit = Decimal('0')
        price_found_key_name = None
        print(f"INFO: (Salam) Attempting to parse price_per_unit. Potential keys: {potential_price_keys}")
        for key_idx, key_name in enumerate(potential_price_keys):
            raw_val = params.get(key_name)
            print(f"INFO: (Salam) Checking price_per_unit key '{key_name}': Raw value is '{raw_val}' (type: {type(raw_val)})")
            if raw_val is not None:
                parsed_decimal_val = to_decimal(raw_val)
                print(f"INFO: (Salam) Key '{key_name}' raw value '{raw_val}' parsed to Decimal: {parsed_decimal_val}")
                if parsed_decimal_val > 0:
                    price_per_unit = parsed_decimal_val
                    price_found_key_name = key_name
                    print(f"INFO: (Salam) VALID price_per_unit found using key '{price_found_key_name}': {price_per_unit}")
                    break
                else:
                    print(f"INFO: (Salam) Price_per_unit key '{key_name}' parsed to {parsed_decimal_val}. Checking next key.")
            if price_per_unit > 0: break
        
        if price_per_unit <= 0 and price_found_key_name is None:
            print(f"WARNING: (Salam) After checking all potential keys, price_per_unit is still {price_per_unit}.")


        currency_symbol_param = "USD" 
        for key in potential_currency_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): currency_symbol_param = str(val).upper(); break
        
        currency_display = f"{currency_symbol_param} " if currency_symbol_param else ""


        # --- Validations ---
        if quantity <= 0: 
            error_msg = "Quantity for Salam contract must be positive and correctly extracted."
            print(f"ERROR: (Salam) Validation Failed: {error_msg}. Final quantity parsed as {quantity}. Key used: '{quantity_found_key_name}'. Searched keys: {potential_quantity_keys}. Params for this request: {params}")
            return None, error_msg
        if price_per_unit <= 0:
            error_msg = "Price per unit for Salam contract must be positive and correctly extracted."
            print(f"ERROR: (Salam) Validation Failed: {error_msg}. Final price_per_unit parsed as {price_per_unit}. Key used: '{price_found_key_name}'. Searched keys: {potential_price_keys}. Params for this request: {params}")
            return None, error_msg
        if asset_description == "Not Specified":
             print(f"WARNING: (Salam) Asset description not found. Searched keys: {potential_asset_desc_keys}. Params: {params}")
        
        # --- Calculations ---
        total_salam_price = quantity * price_per_unit

        # --- Build Structured Output ---
        quantity_display_unit = "units" 
        if asset_description != "Not Specified":
            asset_desc_lower = asset_description.lower()
            if "ton" in asset_desc_lower: quantity_display_unit = "tons"
            elif "kg" in asset_desc_lower: quantity_display_unit = "kg"
            elif "barrel" in asset_desc_lower: quantity_display_unit = "barrels"
            elif "bushel" in asset_desc_lower: quantity_display_unit = "bushels"
            elif "liter" in asset_desc_lower or "litre" in asset_desc_lower : quantity_display_unit = "liters"


        output_structure = {
            "title": f"Salam Contract: Initial Implications for Buyer ({contract_date})",
            "sub_title": salam_rules.get("IntroNote", "Analysis of a Salam contract from the buyer's perspective (e.g., Islamic Bank)."),
            "sections": [
                {
                    "type": "summary_block",
                    "heading": "Salam Contract Details",
                    "items": [
                        {"label": "Contract Date", "value": contract_date},
                        {"label": "Asset to be Purchased", "value": asset_description},
                        {"label": "Quantity", "value": f"{format_display_amount(quantity, '', True, decimal_places=0)} {quantity_display_unit}"},
                        {"label": "Price per Unit", "value": format_display_amount(price_per_unit, currency_display, True, decimal_places=2)},
                        {"label": "Expected Delivery Date", "value": delivery_date},
                    ]
                },
                {
                    "type": "calculation_block",
                    "heading": "1. Calculation of Total Salam Price (Salam Capital)",
                    "steps": [
                        {"label": "Quantity of Goods",
                         "result_value": float(quantity), "result_display": f"{format_display_amount(quantity, '', True, decimal_places=0)} {quantity_display_unit}"},
                        {"label": "Price per Unit",
                         "result_value": float(price_per_unit), "result_display": format_display_amount(price_per_unit, currency_display, True, decimal_places=2)},
                        {"label": "Total Salam Price (Advance Payment by Bank)",
                         "calculation_display": f"{format_display_amount(quantity, '', False, decimal_places=0)} × {format_display_amount(price_per_unit, currency_display, False, decimal_places=2)}", 
                         "result_value": float(total_salam_price), "result_display": format_display_amount(total_salam_price, currency_display, True, decimal_places=2)}
                    ]
                },
                {
                    "type": "journal_entry",
                    "heading": f"2. Journal Entry at Inception of Salam Contract ({contract_date}) - Buyer's Books",
                    "entries": [
                        {"account": "Dr. Salam Asset / Advance for Salam Goods", "amount_display": format_display_amount(total_salam_price, currency_display), "debit": float(total_salam_price), "credit": 0},
                        {"account": "Cr. Cash / Bank", "amount_display": format_display_amount(total_salam_price, currency_display), "debit": 0, "credit": float(total_salam_price)}
                    ],
                    "narrative_below_entries": salam_rules.get("InitialJournalNote", "To record the advance payment for goods to be received under Salam contract.")
                },
                {
                    "type": "information_block",
                    "heading": f"3. Subsequent Accounting (Upon Delivery on {delivery_date})",
                    "content": salam_rules.get("DeliveryNote", 
                        f"Upon delivery of {asset_description.lower()} on or around {delivery_date}, the bank will derecognize the 'Salam Asset' and recognize 'Inventory'. For example:\n"
                        f"Dr. Inventory ({asset_description})   {format_display_amount(total_salam_price, currency_display)}\n"
                        f"Cr. Salam Asset / Advance for Salam Goods   {format_display_amount(total_salam_price, currency_display)}\n"
                        "The inventory will then be available for sale by the bank.")
                }
            ],
            "disclaimer": general_rules.get("CalculationDisclaimer", "Please consult official AAOIFI standards for definitive guidance.")
        }
        print(f"DEBUG: (Salam) Successfully generated Salam output structure.")
        return output_structure, None

    except Exception as e:
        error_msg = f"Unexpected error in Salam transaction implications: {str(e)}"
        print(f"ERROR: (Salam) {error_msg}")
        import traceback; traceback.print_exc()
        return None, error_msg

# --- Istisna'a Contract Implications ---
def calculate_istisnaa_contract_implications(params: dict):
    try:
        print(f"DEBUG: (Istisna'a) Received parameters: {params}")
        istisnaa_rules = RULES_DATA.get("Istisnaa", {}).get("ContractImplications", {})
        general_rules = RULES_DATA.get("General", {})

        potential_contract_date_keys = ["contract_date", "agreement_date", "istisnaa_contract_date", "transaction_date"]
        potential_asset_desc_keys = ["asset_description", "manufactured_asset_description", "custom_asset_description", "item_to_be_manufactured"]
        potential_quantity_keys = ["quantity", "number_of_items", "num_items", "qty", "number_of_assets"] # Added number_of_assets
        potential_cost_per_unit_keys = ["cost_per_unit", "cost_price_per_item", "manufacturer_price_per_unit", "cost_per_desk", "cost_each"]
        potential_sale_price_per_unit_keys = ["sale_price_per_unit", "client_price_per_item", "selling_price_per_unit", "sale_price_each"]
        potential_total_cost_keys = ["total_istisnaa_cost", "cost_to_bank", "manufacturing_cost_for_bank", "total_bank_cost", "total_manufacturing_cost"]
        potential_total_sale_price_keys = ["total_sale_price_to_client", "sale_price_to_client", "parallel_istisnaa_sale_price", "total_client_price"]
        potential_installments_keys = ["number_of_installments_to_manufacturer", "bank_payment_installments", "num_installments_manufacturer"]
        potential_delivery_months_keys = ["delivery_duration_months", "manufacturing_period_months", "expected_completion_months", "timeline_months"]
        potential_currency_keys = ["currency", "currency_code", "ccy"]

        contract_date = "Not Specified"
        for key in potential_contract_date_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): contract_date = str(val); break
        
        asset_description = "Custom Asset"
        for key in potential_asset_desc_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): asset_description = str(val); break

        currency_symbol_param = "USD"
        for key in potential_currency_keys:
            val = params.get(key)
            if val is not None and str(val).strip(): currency_symbol_param = str(val).upper(); break
        currency_display = f"{currency_symbol_param} " if currency_symbol_param else ""

        delivery_duration_months = None
        for key in potential_delivery_months_keys:
            val = params.get(key)
            if val is not None: 
                parsed_val = to_decimal(val)
                if parsed_val > 0: delivery_duration_months = int(parsed_val); break
        
        quantity = Decimal('0')
        quantity_found_key_name = None
        print(f"INFO: (Istisna'a) Attempting to parse quantity. Potential keys: {potential_quantity_keys}")
        for key_name in potential_quantity_keys:
            raw_val = params.get(key_name)
            # print(f"INFO: (Istisna'a) Checking quantity key '{key_name}': Raw value is '{raw_val}'")
            if raw_val is not None:
                parsed_val = to_decimal(raw_val)
                if parsed_val > 0: quantity = parsed_val; quantity_found_key_name = key_name; break
        if quantity_found_key_name: print(f"INFO: (Istisna'a) Quantity found: {quantity} using key '{quantity_found_key_name}'")
        elif any(params.get(qk) for qk in potential_quantity_keys if params.get(qk) is not None) : # A quantity key was present but value was <=0
            print(f"WARNING: (Istisna'a) A quantity key was found, but value parsed to <=0. Quantity set to {quantity}.")
        else: # No quantity key found, assume 1 for single item commissions if asset is described
            if asset_description != "Custom Asset": # Only assume 1 if we have a description
                 print(f"INFO: (Istisna'a) No explicit quantity key found, assuming quantity 1 for single item '{asset_description}'.")
                 quantity = Decimal('1')


        cost_per_unit = Decimal('0')
        cost_pu_found_key_name = None
        if quantity > 0 : # Meaningful to look for per-unit only if quantity > 0
            print(f"INFO: (Istisna'a) Attempting to parse cost_per_unit. Potential keys: {potential_cost_per_unit_keys}")
            for key_name in potential_cost_per_unit_keys:
                raw_val = params.get(key_name)
                if raw_val is not None:
                    parsed_val = to_decimal(raw_val)
                    if parsed_val > 0: cost_per_unit = parsed_val; cost_pu_found_key_name = key_name; break
            if cost_pu_found_key_name: print(f"INFO: (Istisna'a) Cost per unit found: {cost_per_unit} using key '{cost_pu_found_key_name}'")


        total_istisnaa_cost = Decimal('0')
        total_cost_found_key_name = None
        if quantity > 0 and cost_per_unit > 0:
            total_istisnaa_cost = quantity * cost_per_unit
            print(f"INFO: (Istisna'a) Calculated total_istisnaa_cost ({total_istisnaa_cost}) from quantity ({quantity}) and cost_per_unit ({cost_per_unit}).")
        else: 
            print(f"INFO: (Istisna'a) Quantity and/or cost_per_unit not suitable for calculation. Falling back to total cost keys: {potential_total_cost_keys}")
            for key_name in potential_total_cost_keys:
                raw_val = params.get(key_name)
                if raw_val is not None:
                    parsed_val = to_decimal(raw_val)
                    if parsed_val > 0: total_istisnaa_cost = parsed_val; total_cost_found_key_name = key_name; break
            if total_cost_found_key_name: print(f"INFO: (Istisna'a) Total Istisna'a cost found: {total_istisnaa_cost} using key '{total_cost_found_key_name}'")
        
        if total_istisnaa_cost <= 0:
             print(f"WARNING: (Istisna'a) After all checks, total_istisnaa_cost is {total_istisnaa_cost}.")


        has_parallel_istisnaa = any(params.get(key) is not None for key in potential_total_sale_price_keys + potential_sale_price_per_unit_keys)
        sale_price_per_unit = Decimal('0')
        sale_pu_found_key_name = None
        total_sale_price_to_client = Decimal('0')
        total_sale_found_key_name = None

        if has_parallel_istisnaa:
            if quantity > 0: # Meaningful to look for per-unit only if quantity > 0
                print(f"INFO: (Istisna'a) Parallel detected. Attempting to parse sale_price_per_unit. Potential keys: {potential_sale_price_per_unit_keys}")
                for key_name in potential_sale_price_per_unit_keys:
                    raw_val = params.get(key_name)
                    if raw_val is not None:
                        parsed_val = to_decimal(raw_val)
                        if parsed_val > 0: sale_price_per_unit = parsed_val; sale_pu_found_key_name = key_name; break
                if sale_pu_found_key_name: print(f"INFO: (Istisna'a) Sale price per unit found: {sale_price_per_unit} using key '{sale_pu_found_key_name}'")

            if quantity > 0 and sale_price_per_unit > 0:
                total_sale_price_to_client = quantity * sale_price_per_unit
                print(f"INFO: (Istisna'a) Calculated total_sale_price_to_client ({total_sale_price_to_client}) from quantity and sale_price_per_unit.")
            else:
                print(f"INFO: (Istisna'a) Parallel detected, but quantity/sale_price_per_unit not suitable. Falling back to total sale price keys: {potential_total_sale_price_keys}")
                for key_name in potential_total_sale_price_keys:
                    raw_val = params.get(key_name)
                    if raw_val is not None:
                        parsed_val = to_decimal(raw_val)
                        if parsed_val > 0: total_sale_price_to_client = parsed_val; total_sale_found_key_name = key_name; break
                if total_sale_found_key_name: print(f"INFO: (Istisna'a) Total sale price to client found: {total_sale_price_to_client} using key '{total_sale_found_key_name}'")
            
            if total_sale_price_to_client <= 0:
                 print(f"WARNING: (Istisna'a) Parallel Istisna'a indicated, but total_sale_price_to_client is {total_sale_price_to_client}.")


        num_installments_to_manufacturer = Decimal('1') 
        installments_found_key_name = None
        for key_name in potential_installments_keys:
            raw_val = params.get(key_name)
            if key_name in potential_quantity_keys and quantity_found_key_name == key_name : continue # Skip if this key was already used for item quantity
            if raw_val is not None:
                parsed_val = to_decimal(raw_val)
                if parsed_val >= 1: num_installments_to_manufacturer = parsed_val; installments_found_key_name = key_name; break
        if installments_found_key_name: print(f"INFO: (Istisna'a) Number of installments to manufacturer: {num_installments_to_manufacturer} using key '{installments_found_key_name}'")
        else: print(f"INFO: (Istisna'a) Number of installments to manufacturer not specified or found, defaulting to 1.")


        # --- Validations ---
        if total_istisnaa_cost <= 0:
            error_msg = "Total Istisna'a Cost (to Bank) for contract must be positive and correctly extracted/calculated."
            print(f"ERROR: (Istisna'a) Validation Failed: {error_msg}. Final total_istisnaa_cost: {total_istisnaa_cost}. Quantity: {quantity}, CostPU: {cost_per_unit}, TotalCostKeyUsed: '{total_cost_found_key_name if total_cost_found_key_name else 'N/A'}'. Params: {params}")
            return None, error_msg
        
        if has_parallel_istisnaa and total_sale_price_to_client <= 0:
            error_msg = "Total Sale Price to Client for Parallel Istisna'a must be positive if parallel contract exists and correctly extracted/calculated."
            print(f"ERROR: (Istisna'a) Validation Failed: {error_msg}. Final total_sale_price_to_client: {total_sale_price_to_client}. Quantity: {quantity}, SalePU: {sale_price_per_unit}, TotalSaleKeyUsed: '{total_sale_found_key_name if total_sale_found_key_name else 'N/A'}'. Params: {params}")
            return None, error_msg
            
        if has_parallel_istisnaa and total_sale_price_to_client < total_istisnaa_cost:
            print(f"WARNING: (Istisna'a) Parallel Istisna'a total sale price ({total_sale_price_to_client}) is less than total cost to bank ({total_istisnaa_cost}). This implies a loss.")
            
        # --- Calculations ---
        profit_from_parallel_sale = Decimal('0')
        if has_parallel_istisnaa:
            profit_from_parallel_sale = total_sale_price_to_client - total_istisnaa_cost

        installment_to_manufacturer = Decimal('0')
        if num_installments_to_manufacturer > 0 and total_istisnaa_cost > 0 :
            installment_to_manufacturer = (total_istisnaa_cost / num_installments_to_manufacturer).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # --- Build Structured Output ---
        output_structure = {
            "title": f"Istisna'a Contract Implications ({contract_date})",
            "sub_title": istisnaa_rules.get("IntroNote", "Analysis of an Istisna'a contract (and Parallel Istisna'a, if applicable)."),
            "sections": []
        }

        istisnaa_details_items = [
            {"label": "Asset to be Manufactured", "value": asset_description}
        ]
        if quantity > 0 and (cost_per_unit > 0 or total_istisnaa_cost > 0) : # Display quantity if it makes sense
            istisnaa_details_items.append({"label": "Quantity of Items", "value": format_display_amount(quantity, '', True, 0)})
        if cost_per_unit > 0:
            istisnaa_details_items.append({"label": "Cost per Unit (to Bank)", "value": format_display_amount(cost_per_unit, currency_display, True, 2)})
        istisnaa_details_items.append({"label": "Total Cost to Bank (Price to Manufacturer)", "value": format_display_amount(total_istisnaa_cost, currency_display, True, 2)})
        
        if delivery_duration_months is not None:
             istisnaa_details_items.append({"label": "Expected Delivery / Manufacturing Duration", "value": f"{delivery_duration_months} months"})
        
        output_structure["sections"].append({
            "type": "summary_block",
            "heading": "1. Istisna'a Contract with Manufacturer (Bank as Buyer)",
            "items": istisnaa_details_items
        })

        if num_installments_to_manufacturer > 0 and int(num_installments_to_manufacturer) > 1:
            output_structure["sections"].append({
                "type": "calculation_block",
                "heading": "Payment Details to Manufacturer",
                "steps": [
                    {"label": "Total Cost to Bank", "result_value": float(total_istisnaa_cost), "result_display": format_display_amount(total_istisnaa_cost, currency_display, True, 2)},
                    {"label": "Number of Installments to Manufacturer", "result_value": float(num_installments_to_manufacturer), "result_display": str(int(num_installments_to_manufacturer))},
                    {"label": "Each Installment to Manufacturer (approx.)",
                     "calculation_display": f"{format_display_amount(total_istisnaa_cost, '', False, 2)} / {int(num_installments_to_manufacturer)}",
                     "result_value": float(installment_to_manufacturer), "result_display": format_display_amount(installment_to_manufacturer, currency_display, True, 2)}
                ]
            })

        output_structure["sections"].append({
            "type": "journal_entry",
            "heading": "Journal Entry on Contract Signing (Bank's Books - Simplified)",
            "narrative_above_steps": istisnaa_rules.get("InitialJournalNoteBankBuyer", "To recognize the commitment to acquire the asset under Istisna'a. Actual payment entries would occur with installments."),
            "entries": [
                {"account": "Dr. Istisna'a Asset / Work-in-Progress", "amount_display": format_display_amount(total_istisnaa_cost, currency_display), "debit": float(total_istisnaa_cost), "credit": 0},
                {"account": "Cr. Istisna'a Liability (to Manufacturer)", "amount_display": format_display_amount(total_istisnaa_cost, currency_display), "debit": 0, "credit": float(total_istisnaa_cost)}
            ]
        })

        if has_parallel_istisnaa:
            parallel_istisnaa_summary_items = []
            if quantity > 0 and (sale_price_per_unit > 0 or total_sale_price_to_client > 0):
                 parallel_istisnaa_summary_items.append({"label": "Quantity of Items Sold", "value": format_display_amount(quantity, '', True, 0)})
            if sale_price_per_unit > 0:
                 parallel_istisnaa_summary_items.append({"label": "Sale Price per Unit (to Client)", "value": format_display_amount(sale_price_per_unit, currency_display, True, 2)})
            parallel_istisnaa_summary_items.append({"label": "Total Sale Price to Client", "value": format_display_amount(total_sale_price_to_client, currency_display, True, 2)})
            parallel_istisnaa_summary_items.append({"label": "Profit from Parallel Istisna'a", 
                     "value": f"{format_display_amount(profit_from_parallel_sale, currency_display, True, 2)} ({format_display_amount(total_sale_price_to_client, '', False, 2)} - {format_display_amount(total_istisnaa_cost, '', False, 2)})"})

            output_structure["sections"].append({
                "type": "summary_block",
                "heading": "2. Parallel Istisna'a Contract with Client (Bank as Seller)",
                "items": parallel_istisnaa_summary_items
            })
            output_structure["sections"].append({
                "type": "journal_entry",
                "heading": "Journal Entry for Parallel Istisna'a Sale to Client (Bank's Books - Simplified, at time of sale commitment)",
                 "narrative_above_steps": istisnaa_rules.get("ParallelSaleJournalNote", "To record the sale commitment to the client under Parallel Istisna'a."),
                "entries": [
                    {"account": "Dr. Receivable from Client (Parallel Istisna'a)", "amount_display": format_display_amount(total_sale_price_to_client, currency_display), "debit": float(total_sale_price_to_client), "credit": 0},
                    {"account": "Cr. Deferred Istisna'a Revenue / Unearned Revenue", "amount_display": format_display_amount(total_sale_price_to_client, currency_display), "debit": 0, "credit": float(total_sale_price_to_client)}
                ]
            })
        
        output_structure["sections"].append({
            "type": "journal_entry",
            "heading": f"3. Journal Entry on Delivery of Asset from Manufacturer (Bank's Books)",
            "narrative_above_steps": istisnaa_rules.get("DeliveryFromManufacturerNote", "To transfer the manufactured asset to an appropriate asset account."),
            "entries": [
                {"account": f"Dr. Inventory ({asset_description})", "amount_display": format_display_amount(total_istisnaa_cost, currency_display), "debit": float(total_istisnaa_cost), "credit": 0},
                {"account": "Cr. Istisna'a Asset / Work-in-Progress", "amount_display": format_display_amount(total_istisnaa_cost, currency_display), "debit": 0, "credit": float(total_istisnaa_cost)}
            ]
        })

        if has_parallel_istisnaa:
            output_structure["sections"].append({
                "type": "journal_entry",
                "heading": f"4. Journal Entry on Delivery/Sale to Client & Revenue Recognition (Bank's Books)",
                "narrative_above_steps": istisnaa_rules.get("DeliveryToClientNote", "To recognize revenue and cost of goods sold for the Parallel Istisna'a sale."),
                "entries": [
                    {"account": "Dr. Deferred Istisna'a Revenue / Unearned Revenue", "amount_display": format_display_amount(total_sale_price_to_client, currency_display), "debit": float(total_sale_price_to_client), "credit": 0},
                    {"account": "Cr. Istisna'a Sales Revenue", "amount_display": format_display_amount(total_sale_price_to_client, currency_display), "debit": 0, "credit": float(total_sale_price_to_client)},
                    {"account": "Dr. Cost of Goods Sold (Istisna'a)", "amount_display": format_display_amount(total_istisnaa_cost, currency_display), "debit": float(total_istisnaa_cost), "credit": 0},
                    {"account": f"Cr. Inventory ({asset_description})", "amount_display": format_display_amount(total_istisnaa_cost, currency_display), "debit": 0, "credit": float(total_istisnaa_cost)},
                ]
            })

        output_structure["disclaimer"] = general_rules.get("CalculationDisclaimer", "Please consult official AAOIFI standards for definitive guidance. Percentage of Completion method might be required for revenue recognition over time.")
        
        print(f"DEBUG: (Istisna'a) Successfully generated Istisna'a output structure.")
        return output_structure, None

    except Exception as e:
        error_msg = f"Unexpected error in Istisna'a contract implications: {str(e)}"
        print(f"ERROR: (Istisna'a) {error_msg}")
        import traceback; traceback.print_exc()
        return None, error_msg


# --- Stubs/Placeholders for other calculations ---
def calculate_zakat_on_cash_savings(params: dict): 
    return {"title": "Zakat on Cash Savings (Not Implemented)", "details": params}, "Calculation not fully implemented."
import streamlit as st
import pandas as pd
from modules.nlp_qa import QaSystem # Assumes this is updated for multi-standard
from modules.calculations import calculate_murabaha_profit_recognition, generate_murabaha_journal_entries
# You will need to import other calculation functions here as you create them
# e.g., from modules.calculations import calculate_ijarah_income, generate_ijarah_journal_entries

st.set_page_config(page_title="AAOIFI AI Assistant", layout="wide")

# --- 1. LOAD QA SYSTEM (Cached) ---
@st.cache_resource
def load_qa_system():
    """Loads the QaSystem which in turn loads all knowledge base files."""
    try:
        qas = QaSystem(knowledge_base_dir="knowledge_base")
        if not qas.llm_client:
            st.error("LLM Client (e.g., OpenAI) failed to initialize. Please check your API key in .streamlit/secrets.toml and restart.")
        return qas
    except Exception as e:
        st.error(f"Fatal error loading QA system: {e}")
        return None

qa_system = load_qa_system()

# --- 2. APP TITLE AND TABS ---
st.title("📚 AAOIFI AI Assistant Prototype")
st.caption("Your AI-powered guide to understanding and implementing AAOIFI Financial Accounting Standards.")

tab_qa, tab_calculator, tab_journal, tab_compliance = st.tabs([
    "❓ Q&A (All Standards)",
    "🧮 Transaction Calculators",
    "📒 Journal Entry Generators",
    "⚖️ Compliance & Decision (Conceptual)"
])

# --- 3. PREPARE STANDARD LISTS (for dropdowns) ---
available_standards_for_qa = []
available_standards_for_calc_je = [] # Could be a subset if not all have calculators yet

if qa_system and qa_system.standards_data:
    # For Q&A, include all loaded standards
    available_standards_for_qa = sorted(list(qa_system.standards_data.keys()))
    qa_standard_options_display = ["All Standards"] + [s.upper() for s in available_standards_for_qa]

    # For Calculators/JE, you might want a specific list of standards that have these features implemented
    # For now, let's assume all loaded standards *could* have them, and we'll show stubs
    available_standards_for_calc_je = sorted(list(qa_system.standards_data.keys()))
    # Example: If only FAS4 and FAS32 have calculators ready:
    # available_standards_for_calc_je = sorted([k for k,v in qa_system.standards_data.items() if k in ["fas4", "fas32"]])
else:
    qa_standard_options_display = ["All Standards", "FAS4"] # Fallback if nothing loads
    available_standards_for_calc_je = ["fas4"] # Fallback


# --- 4. Q&A TAB ---
with tab_qa:
    st.header("Ask about AAOIFI Financial Accounting Standards")
    st.markdown("Get AI-powered answers based on the official AAOIFI standards text and curated Q&A.")

    col_qa1, col_qa2 = st.columns([1, 3])
    with col_qa1:
        selected_standard_display_qa = st.selectbox(
            "Focus on a specific standard (optional):",
            options=qa_standard_options_display,
            index=0,  # Default to "All Standards"
            key="qa_standard_select"
        )

    selected_standard_key_qa = None
    if selected_standard_display_qa != "All Standards":
        selected_standard_key_qa = selected_standard_display_qa.lower()

    with col_qa2:
        user_question = st.text_input(
            "Enter your question:",
            placeholder=f"e.g., How is lease income recognized in Ijarah?",
            key="qa_user_question"
        )

    if st.button("Get Answer", key="qa_submit_button", type="primary", use_container_width=True):
        if user_question and qa_system:
            if qa_system.llm_client:
                with st.spinner("Thinking... Retrieving context and asking LLM..."):
                    answer, sources = qa_system.answer_question_with_llm(
                        user_question,
                        target_standard=selected_standard_key_qa
                    )
                st.markdown("---")
                st.subheader(f"Response (Focus: {selected_standard_display_qa}):")
                st.markdown(answer)
                if sources:
                    st.markdown("---")
                    st.markdown("##### Retrieved Context / Sources for LLM:")
                    st.text_area("Context Used:", value=sources, height=150, disabled=True, key="qa_sources_display")
            else:
                st.error("LLM Client is not available. Please check your API key and app logs.")
        elif not user_question:
            st.warning("Please enter a question.")
        elif not qa_system:
            st.error("The Q&A system is not loaded. Please check application startup logs.")

# --- 5. TRANSACTION CALCULATORS TAB ---
with tab_calculator:
    st.header("Financial Transaction Calculators")
    st.markdown("Perform calculations specific to different AAOIFI standards.")

    if not available_standards_for_calc_je:
        st.warning("No standards available for calculation. Please check knowledge base.")
    else:
        calc_standard_selected_display = st.selectbox(
            "Select Standard for Calculation:",
            options=[s.upper() for s in available_standards_for_calc_je],
            key="calc_standard_select"
        )
        calc_standard_key = calc_standard_selected_display.lower() if calc_standard_selected_display else None

        st.markdown("---")

        if calc_standard_key == "fas4":
            st.subheader("FAS 4: Murabaha Profit Recognition Calculator")
            with st.form(key="murabaha_calc_form"):
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    cost_price_calc = st.number_input("Cost Price of Asset to Bank", min_value=0.01, value=10000.0, step=100.0, format="%.2f", key="m_cost")
                    sale_price_calc = st.number_input("Sale Price to Customer (Cost + Profit)", min_value=float(cost_price_calc) if cost_price_calc >0 else 0.01, value=12000.0, step=100.0, format="%.2f", key="m_sale")
                with col_c2:
                    num_installments_calc = st.number_input("Number of Installments (if deferred)", min_value=1, value=12, step=1, key="m_install")
                    down_payment_calc = st.number_input("Down Payment by Customer (if any)", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="m_dp", max_value=float(sale_price_calc) if sale_price_calc else 0.0)
                submit_button_calc = st.form_submit_button(label="Calculate Murabaha Schedule")

            if submit_button_calc:
                # Validation
                valid_input = True
                if cost_price_calc <= 0:
                    st.error("Cost price must be greater than zero.")
                    valid_input = False
                if sale_price_calc < cost_price_calc:
                    st.error("Sale Price must be greater than or equal to Cost Price.")
                    valid_input = False
                if down_payment_calc > sale_price_calc :
                    st.error("Down payment cannot exceed sale price.")
                    valid_input = False

                if valid_input:
                    schedule_df, error_msg = calculate_murabaha_profit_recognition(cost_price_calc, sale_price_calc, num_installments_calc, down_payment_calc)
                    if error_msg:
                        st.error(error_msg)
                    elif schedule_df is not None:
                        st.success("Murabaha Profit Recognition Schedule:")
                        st.dataframe(schedule_df.style.format("{:.2f}", subset=pd.IndexSlice[:, ['Installment Amount', 'Principal Repaid', 'Profit Recognized', 'Cumulative Profit Recognized', 'Outstanding Balance']]))
                        total_profit_calc = sale_price_calc - cost_price_calc
                        st.metric("Total Murabaha Profit", f"{total_profit_calc:.2f}")
                        if not schedule_df.empty and 'Installment Amount' in schedule_df.columns and len(schedule_df) > 0:
                            st.metric("Installment Amount", f"{schedule_df['Installment Amount'].iloc[0]:.2f}")
                    else:
                        st.error("Could not calculate the Murabaha schedule. Please verify inputs.")
        
        elif calc_standard_key == "fas32": # IJARAH
            st.subheader("FAS 32: Ijarah Income Recognition (Conceptual)")
            st.info("Ijarah calculation logic and UI form are not yet implemented in this prototype.")
            # TODO: Add Ijarah calculator form here (inputs for lease amount, term, rental, residual value for IMBT etc.)
            #       And call your `calculate_ijarah_income(...)` function.

        elif calc_standard_key == "fas7": # SALAM
            st.subheader("FAS 7: Salam Accounting Aspects (Conceptual)")
            st.info("Salam calculation logic and UI form are not yet implemented in this prototype.")
            # TODO: Add Salam calculator/logic form here.

        elif calc_standard_key == "fas10": # ISTISNA'A
            st.subheader("FAS 10: Istisna'a Percentage of Completion (Conceptual)")
            st.info("Istisna'a PoC calculation logic and UI form are not yet implemented.")
            # TODO: Add Istisna'a PoC calculator form.

        elif calc_standard_key == "fas28": # Murabaha Amendments
            st.subheader("FAS 28: Murabaha Amendments Considerations")
            st.info("FAS 28 provides amendments to FAS 4. Specific calculations for amendments can be integrated with the FAS 4 calculator or as separate checks.")

        else:
            st.info(f"Calculator for {calc_standard_selected_display} not implemented yet.")

# --- 6. JOURNAL ENTRY GENERATORS TAB ---
with tab_journal:
    st.header("Automated Journal Entry Generators")
    st.markdown("Generate standard accounting entries based on transaction details for different AAOIFI standards.")

    if not available_standards_for_calc_je:
        st.warning("No standards available for journal entry generation. Please check knowledge base.")
    else:
        je_standard_selected_display = st.selectbox(
            "Select Standard for Journal Entry Generation:",
            options=[s.upper() for s in available_standards_for_calc_je],
            key="je_standard_select"
        )
        je_standard_key = je_standard_selected_display.lower() if je_standard_selected_display else None
        
        st.markdown("---")

        if je_standard_key == "fas4":
            st.subheader("FAS 4: Murabaha Initial Journal Entries")
            with st.form(key="murabaha_je_form"):
                col_j1, col_j2 = st.columns(2)
                with col_j1:
                    cost_price_je = st.number_input("Cost Price of Asset to Bank", min_value=0.01, value=50000.0, step=100.0, key="m_je_cost", format="%.2f")
                    sale_price_je = st.number_input("Sale Price to Customer", min_value=float(cost_price_je) if cost_price_je > 0 else 0.01, value=60000.0, step=100.0, key="m_je_sale", format="%.2f")
                with col_j2:
                    down_payment_je = st.number_input("Down Payment by Customer (JE)", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="m_je_dp", max_value=float(sale_price_je) if sale_price_je else 0.0)
                    customer_name_je = st.text_input("Customer Name (Optional)", "Valued Customer", key="m_je_customer")
                submit_button_je = st.form_submit_button(label="Generate Murabaha Journal Entries")

            if submit_button_je:
                # Validation
                valid_je_input = True
                if cost_price_je <=0:
                    st.error("Cost price must be greater than zero for journal entries.")
                    valid_je_input = False
                if sale_price_je < cost_price_je:
                    st.error("Sale Price must be greater than or equal to Cost Price for journal entries.")
                    valid_je_input = False
                if down_payment_je > sale_price_je:
                    st.error("Down payment cannot exceed sale price for journal entries.")
                    valid_je_input = False

                if valid_je_input:
                    entries_df, error_msg_je = generate_murabaha_journal_entries(cost_price_je, sale_price_je, down_payment_je, customer_name_je)
                    if error_msg_je:
                        st.error(error_msg_je)
                    elif entries_df is not None:
                        st.success("Generated Initial Murabaha Journal Entries:")
                        st.dataframe(entries_df.style.format({"Debit": "{:.2f}", "Credit": "{:.2f}"}), hide_index=True)
                        st.markdown("---")
                        st.markdown("""
                        **Explanation:** These are typical entries for initiating a Murabaha transaction. 
                        Periodic entries for profit recognition and installment collection would follow.
                        """)
                    else:
                        st.error("Could not generate Murabaha journal entries. Please verify inputs.")
        
        elif je_standard_key == "fas32": # IJARAH
            st.subheader("FAS 32: Ijarah Journal Entries (Conceptual)")
            st.info("Ijarah journal entry generation logic and UI form are not yet implemented.")
            # TODO: Add Ijarah JE form and call `generate_ijarah_journal_entries(...)`.

        elif je_standard_key == "fas7": # SALAM
            st.subheader("FAS 7: Salam Journal Entries (Conceptual)")
            st.info("Salam journal entry generation logic and UI form are not yet implemented.")

        elif je_standard_key == "fas10": # ISTISNA'A
            st.subheader("FAS 10: Istisna'a Journal Entries (Conceptual)")
            st.info("Istisna'a journal entry generation logic and UI form are not yet implemented.")

        elif je_standard_key == "fas28":
            st.subheader("FAS 28: Journal Entries for Murabaha Amendments")
            st.info("Integrate specific journal entry impacts of FAS 28 with FAS 4 or as separate examples.")
            
        else:
            st.info(f"Journal entry generator for {je_standard_selected_display} not implemented yet.")

# --- 7. COMPLIANCE & DECISION SUPPORT TAB (Conceptual) ---
with tab_compliance:
    st.header("Compliance Checker & Decision Support (Conceptual)")
    st.markdown("""
    This section is a placeholder for more advanced AI features.
    - **Compliance Checker:** Could involve uploading transaction data or journal entries, and the AI would attempt to validate them against rules extracted from AAOIFI standards.
    - **Decision Support:** Could help with classifying complex transactions or choosing the correct accounting treatment based on scenario details.
    """)
    
    st.info("These advanced features require significant development of rule engines, expert systems, or more sophisticated NLP/ML models and are not part of the current prototype's core functionality.")

    st.subheader("Example: Murabaha Basic Compliance Checklist (Illustrative)")
    if st.checkbox("Does the transaction involve a genuine sale of an asset?"):
        pass
    if st.checkbox("Is the cost price to the seller (Bank) clearly known and disclosed?"):
        pass
    if st.checkbox("Is the profit mark-up (Ribh) clearly agreed upon at the outset?"):
        pass
    if st.checkbox("Does the Bank take constructive or physical possession of the asset before selling to the customer?"):
        pass
    
    # You could expand this with more complex logic based on standard selection

# --- 8. SIDEBAR ---
st.sidebar.header("About This AI Assistant")
st.sidebar.info(
    "This is an AI-powered prototype designed to assist with understanding and implementing "
    "AAOIFI Financial Accounting Standards.\n\n"
    "**Current Focus:**\n"
    "- FAS 4 (Murabaha) - Implemented\n"
    "- FAS 7 (Salam) - Conceptual\n"
    "- FAS 10 (Istisna'a) - Conceptual\n"
    "- FAS 28 (Murabaha Amend.) - Conceptual\n"
    "- FAS 32 (Ijarah) - Conceptual\n\n"
    "It uses a local knowledge base for context retrieval and an LLM (OpenAI API via Streamlit Secrets) "
    "for generating natural language responses in the Q&A section."
)
st.sidebar.image("https://www.aaoifi.com/wp-content/uploads/2020/05/logo-AAOIFI.png", width=150) # Replace with a generic logo or remove if not appropriate
st.sidebar.warning(
    "**DISCLAIMER:** This is a PROTOTYPE for demonstration and educational purposes ONLY. "
    "It is NOT a substitute for professional financial advice or the official AAOIFI standards. "
    "Always consult qualified professionals and refer to the complete official standards for "
    "actual financial reporting and decision-making. Ensure your API key is kept secure and you "
    "understand any costs associated with LLM API usage."
)

if not qa_system:
    st.error("The core Q&A system failed to load. Please check the console logs for more details, ensure Python environment is correct, and required files are present.")
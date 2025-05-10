import pandas as pd
import json
import os
import sys

# Add project root to sys.path to allow importing models.classifier
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from models.classifier import StandardsClassifier # noqa: E402

def create_finetuning_data(csv_file_path: str, 
                           standards_json_path: str, 
                           translations_json_path: str, 
                           output_jsonl_path: str):
    """
    Generates fine-tuning data in JSONL format from a CSV file.
    Each line in the output JSONL file will be a JSON object representing a single training example.
    The format is: {"messages": [{"role": "system", "content": ...}, {"role": "user", "content": ...}, {"role": "assistant", "content": ...}]}
    """
    try:
        df = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_file_path}")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # Initialize classifier to use its _build_ai_prompt method
    # No API key needed here as we are only building prompts, not making calls
    # Pass dummy key or handle client initialization if StandardsClassifier requires it strictly
    temp_openai_key = os.getenv("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")
    if not temp_openai_key:
        print("Warning: OPENAI_API_KEY not set. Prompt generation might be affected if client is strictly needed for it.")
        # If StandardsClassifier client is essential for prompt building, this might fail or need a mock.
        # For now, assuming _build_ai_prompt doesn't directly use the client.
    
    try:
        classifier = StandardsClassifier(
            standards_file=standards_json_path,
            translations_file=translations_json_path
        )
    except FileNotFoundError as e:
        print(f"Error initializing StandardsClassifier: {e}. Make sure paths to standards and translations JSON are correct.")
        return


    finetuning_data = []

    for index, row in df.iterrows():
        transaction_text = str(row['Transaction_Description'])
        fas_code_raw = str(row['FAS_Code'])
        confidence = float(row['Confidence_Level'])

        # Normalize FAS_Code (e.g., "FAS 4" -> "FAS4")
        fas_code_normalized = fas_code_raw.replace(" ", "")

        if fas_code_normalized not in classifier.standards:
            print(f"Warning: FAS_Code '{fas_code_normalized}' from CSV (row {index+2}) not found in standards.json. Skipping this row.")
            continue
        
        # Detect language (assuming CSV descriptions are English for fine-tuning prompt consistency)
        # If your CSV contains Arabic, this needs adjustment or separate fine-tuning sets.
        language = 'en' # Forcing English for prompt consistency based on CSV data.
                        # If you have Arabic data for fine-tuning, handle language detection.

        # Get system and user prompt using classifier's logic
        try:
            system_message, user_prompt = classifier._build_ai_prompt(transaction_text, language)
        except Exception as e:
            print(f"Error building AI prompt for row {index+2}: {e}")
            continue

        # Create the assistant's message (the expected output)
        # The model is expected to return a JSON with scores.
        # For training, we provide the primary standard from CSV with its confidence.
        # The prompt instructs the model that scores should sum to 1.0.
        # The model should learn to adjust or infer other scores.
        assistant_completion = {fas_code_normalized: confidence}
        
        # OpenAI expects the assistant's content to be a string (JSON string in this case)
        assistant_content_str = json.dumps(assistant_completion)

        finetuning_data.append({
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": assistant_content_str}
            ]
        })

    # Write to JSONL file
    try:
        with open(output_jsonl_path, 'w', encoding='utf-8') as f:
            for item in finetuning_data:
                f.write(json.dumps(item) + '\n')
        print(f"Successfully created fine-tuning data at {output_jsonl_path}")
        print(f"Generated {len(finetuning_data)} training examples.")
    except IOError:
        print(f"Error: Could not write to output file {output_jsonl_path}")


if __name__ == "__main__":
    # Assuming the script is run from the project root, e.g., `python scripts/prepare_finetune_data.py`
    # Adjust paths if necessary based on your execution context.
    
    # Path to the input CSV file
    csv_path = os.path.join(project_root, "data", "objective_2_fas_identification.csv")
    
    # Paths to standards and translations (needed by StandardsClassifier for prompt generation)
    standards_path = os.path.join(project_root, "data", "standards.json")
    translations_path = os.path.join(project_root, "data", "translations.json")
    
    # Path for the output JSONL file
    output_path = os.path.join(project_root, "data", "finetuning_data.jsonl")

    print(f"Project root: {project_root}")
    print(f"CSV input file: {csv_path}")
    print(f"Standards JSON: {standards_path}")
    print(f"Translations JSON: {translations_path}")
    print(f"Output JSONL file: {output_path}")

    create_finetuning_data(csv_path, standards_path, translations_path, output_path)

    print("\nNext steps for fine-tuning:")
    print("1. Ensure your OPENAI_API_KEY environment variable is set.")
    print(f"2. Upload the generated file '{output_path}' to OpenAI:")
    print("   `response = client.files.create(file=open('data/finetuning_data.jsonl', 'rb'), purpose='fine-tune')`")
    print("   `file_id = response.id`")
    print("3. Create a fine-tuning job (e.g., for 'gpt-4-turbo-0125'):")
    print("   `client.fine_tuning.jobs.create(training_file=file_id, model='gpt-4')`")
    print("4. Monitor the job. Once complete, you'll get a fine-tuned model ID.")
    print("5. Set the `FINE_TUNED_MODEL_ID` environment variable to this new ID before running your Flask app.")
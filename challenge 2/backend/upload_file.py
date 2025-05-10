import os
from openai import OpenAI

EXPECTED_KEY_NAME = "OPENAI_API_KEY"
api_key = None # Initialize to None

print(f"Attempting to retrieve environment variable: '{EXPECTED_KEY_NAME}'")

# Method 1: Using os.getenv()
retrieved_with_getenv = os.getenv(EXPECTED_KEY_NAME)
print(f"Value from os.getenv('{EXPECTED_KEY_NAME}'): '{retrieved_with_getenv}' (Type: {type(retrieved_with_getenv)})")

# Method 2: Direct dictionary access (more explicit about key matching)
retrieved_with_direct_access = None
if EXPECTED_KEY_NAME in os.environ:
    retrieved_with_direct_access = os.environ[EXPECTED_KEY_NAME]
    print(f"Value from os.environ['{EXPECTED_KEY_NAME}']: '{retrieved_with_direct_access}' (Type: {type(retrieved_with_direct_access)})")
else:
    print(f"Key '{EXPECTED_KEY_NAME}' NOT FOUND in os.environ dictionary keys.")

# Determine which value to use for api_key
if retrieved_with_getenv:
    api_key = retrieved_with_getenv
elif retrieved_with_direct_access:
    print("os.getenv() failed but direct access worked. Using value from direct access.")
    api_key = retrieved_with_direct_access
else:
    # If both failed, print detailed diagnostic for os.environ
    print(f"\n--- Detailed os.environ Diagnostic for '{EXPECTED_KEY_NAME}' ---")
    key_found_case_insensitive = False
    for k, v_env in os.environ.items():
        # Print representation of key and our expected key to see differences
        print(f"Checking os.environ key: {repr(k)} (len {len(k)}) against expected: {repr(EXPECTED_KEY_NAME)} (len {len(EXPECTED_KEY_NAME)})")
        if k == EXPECTED_KEY_NAME:
            print(f"  EXACT MATCH FOUND IN LOOP: os.environ['{k}'] = '{v_env[:10]}...'")
            # This should have been caught by 'if EXPECTED_KEY_NAME in os.environ'
            break 
        if k.upper() == EXPECTED_KEY_NAME.upper():
            key_found_case_insensitive = True
            print(f"  CASE INSENSITIVE MATCH: '{k}' (actual) vs '{EXPECTED_KEY_NAME}' (expected)")
    if not key_found_case_insensitive:
         print(f"No variant of '{EXPECTED_KEY_NAME}' found in os.environ keys.")
    print("-----------------------------------------------------------------\n")


if not api_key or not api_key.strip(): # Also check if it's just whitespace
    print(f"Error: OPENAI_API_KEY resolved to empty or None ('{api_key}'). Please ensure it's correctly set and accessible.")
else:
    print(f"Successfully resolved OPENAI_API_KEY: {api_key[:10]}... (truncated)")
    client = OpenAI(api_key=api_key)
    print("OpenAI client initialized.")
    try:
        print("Attempting to upload finetuning_data.jsonl...")
        file_response = client.files.create(
            file=open("data/finetuning_data.jsonl", "rb"), 
            purpose="fine-tune"
        )
        file_id = file_response.id
        print(f"File uploaded successfully! File ID: {file_id}")
    except Exception as e:
        print(f"Error uploading file: {e}")
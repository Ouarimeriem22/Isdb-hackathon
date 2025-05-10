import os
from openai import OpenAI

# Step 1: Retrieve the API Key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

# Step 2: Check if the API Key was found
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set.")
    print("Please set it before running the script, e.g.:")
    print("export OPENAI_API_KEY='sk-your_key_here'")
else:
    # Step 3: Initialize the OpenAI client if the API key is present
    print(f"OPENAI_API_KEY found: {api_key[:10]}... (truncated)") # Confirm key is read
    client = OpenAI(api_key=api_key)
    print("OpenAI client initialized.")
    
    # Step 4: Define your Training File ID and the Base Model for fine-tuning
    # IMPORTANT: Replace "YOUR_FILE_ID_HERE" with the actual File ID you got after uploading.
    # You had: "file-SezTAzBq6VpBYgwjxuhsgs"
    TRAINING_FILE_ID = "file-SezTAzBq6VpBYgwjxuhsgs" # Make sure this is your correct, uploaded File ID

    # Choose a GPT-3.5 Turbo model available for fine-tuning
    # Common options include "gpt-3.5-turbo-0125" or "gpt-3.5-turbo-1106".
    # Always check the latest OpenAI documentation for available models.
    BASE_MODEL_FOR_FINETUNING = "gpt-3.5-turbo-0125" 

    # Step 5: Attempt to create the fine-tuning job
    try:
        print(f"\nAttempting to create fine-tuning job with:")
        print(f"  Training File ID: {TRAINING_FILE_ID}")
        print(f"  Base Model:       {BASE_MODEL_FOR_FINETUNING}")
        
        job_response = client.fine_tuning.jobs.create(
            training_file=TRAINING_FILE_ID,
            model=BASE_MODEL_FOR_FINETUNING
        )
        
        job_id = job_response.id
        print(f"\nFine-tuning job started successfully!")
        print(f"Job ID: {job_id}")
        print(f"Status: {job_response.status}") # Initial status
        
        print(f"\nYou can monitor the job status by:")
        print(f"1. Visiting the OpenAI platform (Fine-tuning section).")
        print(f"2. Using the OpenAI API: client.fine_tuning.jobs.retrieve('{job_id}')")
        
    except Exception as e:
        print(f"\nError creating fine-tuning job: {e}")
        print("Please check the following:")
        print(f"  - Is the TRAINING_FILE_ID '{TRAINING_FILE_ID}' correct and accessible in your OpenAI account?")
        print(f"  - Is the model '{BASE_MODEL_FOR_FINETUNING}' valid and available for fine-tuning?")
        print(  "  - Do you have sufficient credits/quota in your OpenAI account?")
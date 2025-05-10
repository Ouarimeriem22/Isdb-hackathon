import os
import time # For adding delays
from openai import OpenAI

# --- Configuration ---
JOB_ID = "ftjob-wGXTmejzqQmo4Bl6b8MwI028" # YOUR JOB ID
CHECK_INTERVAL_SECONDS = 300 # Check every 60 seconds (1 minute)
# --- End Configuration ---

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set.")
else:
    client = OpenAI(api_key=api_key)
    print(f"Monitoring Job ID: {JOB_ID}")
    print(f"Checking status every {CHECK_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.\n")

    try:
        while True:
            job_details = client.fine_tuning.jobs.retrieve(JOB_ID)
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
            print(f"[{current_time}] Status: {job_details.status}")

            if job_details.fine_tuned_model:
                print(f"  Fine-tuned Model ID: {job_details.fine_tuned_model}")
            
            if job_details.error:
                 print(f"  Error details: {job_details.error}")

            if job_details.status == "succeeded":
                print("\n-------------------------------------")
                print("🎉 Fine-tuning job SUCCEEDED! 🎉")
                print(f"Fine-tuned Model ID: {job_details.fine_tuned_model}")
                print("-------------------------------------")
                break # Exit the loop
            elif job_details.status == "failed":
                print("\n-------------------------------------")
                print("❌ Fine-tuning job FAILED! ❌")
                if job_details.error:
                    print(f"Error Code: {job_details.error.get('code')}")
                    print(f"Error Message: {job_details.error.get('message')}")
                    print(f"Error Param: {job_details.error.get('param')}")
                print("-------------------------------------")
                break # Exit the loop
            elif job_details.status == "cancelled":
                print("\n-------------------------------------")
                print("🚫 Fine-tuning job CANCELLED. 🚫")
                print("-------------------------------------")
                break # Exit the loop
            
            time.sleep(CHECK_INTERVAL_SECONDS) # Wait before checking again

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
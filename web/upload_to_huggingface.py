import os
from datasets import load_dataset
from huggingface_hub import login

def upload_to_hf():
    print("=== PayPal to Hugging Face Dataset Uploader ===")
    
    # Check for Hugging Face Token
    token = os.environ.get("HF_TOKEN")
    if token:
        print("Logging into Hugging Face...")
        login(token=token)
    else:
        print("ERROR: Please set your HF_TOKEN environment variable.")
        print("Example: export HF_TOKEN='your_hf_token'")
        return

    dataset_name = os.environ.get("DATASET_NAME")
    if not dataset_name:
        dataset_name = input("Enter your desired Hugging Face dataset repo name (e.g., your_username/paypal-hackathon-data): ")

    
    # Check if we have gathered any live data yet
    data_file = "paypal_live_data.jsonl"
    if not os.path.exists(data_file):
        print(f"\nError: {data_file} not found.")
        print("You need to make some test transactions on your Next.js checkout page first so the backend logs them!")
        return

    print("\nLoading local JSONL data gathered from live PayPal checkouts...")
    try:
        # Load the gathered JSONL file as a Hugging Face Dataset
        dataset = load_dataset('json', data_files={'train': data_file})
        
        print(f"Found {len(dataset['train'])} rows of transaction data.")
        print(f"Uploading to {dataset_name} on Hugging Face Hub...")
        
        # Push to Hugging Face
        dataset.push_to_hub(dataset_name)
        
        print("\n✅ Upload complete!")
        print(f"You can view your dataset at: https://huggingface.co/datasets/{dataset_name}")
        
    except Exception as e:
        print(f"\nAn error occurred during upload: {e}")
        print("Make sure you have the 'datasets' and 'huggingface_hub' libraries installed: pip install datasets huggingface_hub")

if __name__ == "__main__":
    upload_to_hf()

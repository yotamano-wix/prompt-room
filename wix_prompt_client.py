"""
Wix AI Gateway Prompt Client
============================
This script sends requests to the Wix AI Gateway to generate content using prompts.

Usage:
1. Edit config.json with your credentials:
   - app_id: Your Wix application ID
   - secret_key: Your app's secret key
   - prompt_id: The ID of the prompt you want to use
   - params: The parameters your prompt expects

2. Run: python wix_prompt_client.py
"""

from typing import Dict, Any, Optional
import json
import requests
from wix_server_signer.server_signer import ServerSigner


# API Configuration
WIX_URL_INTERNAL: str = "http://api.42.wixprod.net"
WIX_AI_GATEWAY_URL = f'{WIX_URL_INTERNAL}/wix-ai-gateway/v1'
GENERATE_PROMPT_BY_CONTENT = f'{WIX_AI_GATEWAY_URL}/generate-content-by-prompt'


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def sync_request(api_url: str, method: str, json_data: Dict[str, Any], headers: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make a synchronous HTTP request."""
    try:
        response = requests.request(
            method=method,
            url=api_url,
            timeout=None,
            json=json_data,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise e


def get_headers(app_id: str, secret_key: str) -> Dict[str, Any]:
    """Generate authentication headers using ServerSigner."""
    return ServerSigner(app_def_id=app_id, app_secret=secret_key).sign_app()


def get_llm_response_to_prompt_by_text(
    prompt_json: Dict[str, Any],
    prompt_id: str,
    app_id: str,
    secret_key: str
) -> Optional[Dict[str, Any]]:
    """Send a prompt request to the Wix AI Gateway and get the LLM response."""
    return sync_request(
        api_url=f"{GENERATE_PROMPT_BY_CONTENT}/{prompt_id}",
        method='POST',
        json_data=prompt_json,
        headers=get_headers(app_id, secret_key)
    )


def main():
    # Load configuration
    config = load_config()
    
    app_id = config["app_id"]
    secret_key = config["secret_key"]
    prompt_id = config["prompt_id"]
    params = config.get("params", {})
    
    # Validate configuration
    if app_id == "YOUR_APP_ID_HERE" or not app_id:
        print("❌ Error: Please set your app_id in config.json")
        return
    if secret_key == "YOUR_SECRET_KEY_HERE" or not secret_key:
        print("❌ Error: Please set your secret_key in config.json")
        return
    if prompt_id == "YOUR_PROMPT_ID_HERE" or not prompt_id:
        print("❌ Error: Please set your prompt_id in config.json")
        return
    
    # Build the prompt JSON
    prompt_json = {
        "params": params,
        "prompt_id": prompt_id
    }
    
    print(f"🚀 Sending request to Wix AI Gateway...")
    print(f"   Prompt ID: {prompt_id}")
    print(f"   Parameters: {params}")
    print()
    
    try:
        llm_response = get_llm_response_to_prompt_by_text(
            prompt_json=prompt_json,
            prompt_id=prompt_id,
            app_id=app_id,
            secret_key=secret_key
        )
        
        # Print the generated text
        print("✅ Response received!\n")
        print("-" * 50)
        print("Generated Content:")
        print("-" * 50)
        
        for text in llm_response['response']['generatedContent']['texts']:
            print(text)
        
        # Uncomment to see the full response:
        # print("\nFull Response:")
        # print(json.dumps(llm_response, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except KeyError as e:
        print(f"❌ Unexpected response format. Missing key: {e}")
        print("Full response:", llm_response)


if __name__ == "__main__":
    main()

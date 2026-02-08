"""
Pipeline Test Runner
====================
Run and chain prompts through the Wix AI Gateway for testing.

Usage:
  # Run a single prompt with default test data
  python pipeline_test.py run copier
  
  # Run a predefined scenario (recommended)
  python pipeline_test.py scenario copier_only
  python pipeline_test.py scenario user_image_flow      # Copier → Curator
  python pipeline_test.py scenario full_pipeline        # Copier → Curator → Architect
  
  # Compare last two runs of a prompt
  python pipeline_test.py diff copier
  
  # List all saved results
  python pipeline_test.py list
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from wix_server_signer.server_signer import ServerSigner

# ============================================================================
# CONFIGURATION
# ============================================================================

def load_prompts_config():
    """Load prompt IDs, scenarios, and default test data from config file (versionable)"""
    with open("prompts_config.json", "r") as f:
        config = json.load(f)
    return config["prompts"], config["scenarios"], config.get("default_test_data", {})

PROMPTS, SCENARIOS, DEFAULT_TEST_DATA = load_prompts_config()

# ============================================================================
# API CLIENT
# ============================================================================

WIX_URL = "http://api.42.wixprod.net/wix-ai-gateway/v1/generate-content-by-prompt"

def load_credentials() -> tuple:
    """Load app credentials from config.json"""
    with open("config.json", "r") as f:
        config = json.load(f)
    return config["app_id"], config["secret_key"]

def call_prompt(prompt_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call a prompt via the Wix AI Gateway"""
    app_id, secret_key = load_credentials()
    
    headers = ServerSigner(app_def_id=app_id, app_secret=secret_key).sign_app()
    headers = {k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in headers.items()}
    
    response = requests.post(
        f"{WIX_URL}/{prompt_id}",
        json={"params": params, "prompt_id": prompt_id},
        headers=headers,
        timeout=120
    )
    response.raise_for_status()
    return response.json()

# ============================================================================
# RESULTS MANAGEMENT
# ============================================================================

RESULTS_DIR = Path("test_results")

def save_result(prompt_name: str, result: Dict[str, Any], params: Dict[str, Any]) -> Path:
    """Save a test result with timestamp"""
    RESULTS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prompt_name}_{timestamp}.json"
    filepath = RESULTS_DIR / filename
    
    # Extract the generated text from the response
    generated_text = ""
    if "response" in result and "generatedContent" in result["response"]:
        texts = result["response"]["generatedContent"].get("texts", [])
        if texts:
            generated_text = texts[0] if isinstance(texts[0], str) else texts[0].get("generatedText", "")
    elif "generatedText" in result.get("response", {}).get("generatedContent", {}):
        generated_text = result["response"]["generatedContent"]["generatedText"]
    
    # Handle nested structure
    if isinstance(generated_text, dict):
        generated_text = generated_text.get("generatedText", str(generated_text))
    
    data = {
        "prompt": prompt_name,
        "timestamp": timestamp,
        "params": params,
        "raw_response": result,
        "output": generated_text
    }
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    # Also save a .md version for easy reading
    md_filepath = RESULTS_DIR / f"{prompt_name}_{timestamp}.md"
    with open(md_filepath, "w") as f:
        f.write(f"# {prompt_name} - {timestamp}\n\n")
        f.write(f"## Parameters\n```json\n{json.dumps(params, indent=2)}\n```\n\n")
        f.write(f"## Output\n{generated_text}\n")
    
    return filepath

def get_latest_result(prompt_name: str) -> Optional[Dict[str, Any]]:
    """Get the most recent result for a prompt"""
    if not RESULTS_DIR.exists():
        return None
    
    files = sorted(RESULTS_DIR.glob(f"{prompt_name}_*.json"), reverse=True)
    if not files:
        return None
    
    with open(files[0], "r") as f:
        return json.load(f)

def get_last_n_results(prompt_name: str, n: int = 2) -> List[Dict[str, Any]]:
    """Get the last N results for comparison"""
    if not RESULTS_DIR.exists():
        return []
    
    files = sorted(RESULTS_DIR.glob(f"{prompt_name}_*.json"), reverse=True)[:n]
    results = []
    for f in files:
        with open(f, "r") as file:
            results.append(json.load(file))
    return results

# ============================================================================
# COMMANDS
# ============================================================================

def run_prompt(prompt_name: str, extra_params: Optional[Dict[str, Any]] = None, use_defaults: bool = False) -> Dict[str, Any]:
    """Run a single prompt"""
    if prompt_name not in PROMPTS:
        print(f"❌ Unknown prompt: {prompt_name}")
        print(f"   Available: {', '.join(PROMPTS.keys())}")
        sys.exit(1)
    
    prompt_config = PROMPTS[prompt_name]
    
    # Build params
    if use_defaults:
        params = filter_params_for_prompt(prompt_name, DEFAULT_TEST_DATA)
    else:
        params = extra_params or {}
    
    print(f"\n🚀 Running: {prompt_config['name']}")
    print(f"   Prompt ID: {prompt_config['id']}")
    print(f"   Params: {list(params.keys()) if params else '(none)'}")
    
    try:
        result = call_prompt(prompt_config["id"], params)
        filepath = save_result(prompt_name, result, params)
        
        print(f"✅ Success! Saved to: {filepath}")
        print(f"   Also saved: {filepath.with_suffix('.md')}")
        
        return get_latest_result(prompt_name)
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        raise

def filter_params_for_prompt(prompt_name: str, all_params: Dict[str, Any]) -> Dict[str, Any]:
    """Filter params to only include those the prompt accepts"""
    prompt_config = PROMPTS.get(prompt_name, {})
    accepted_params = prompt_config.get("params", [])
    
    if not accepted_params:
        # If no params defined, pass all
        return all_params
    
    return {k: v for k, v in all_params.items() if k in accepted_params}


def run_chain(prompt_names: List[str], base_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a chain of prompts, passing outputs to inputs"""
    accumulated_params = dict(base_params or {})
    last_result = None
    
    print(f"\n🔗 Running chain: {' → '.join(prompt_names)}")
    print("=" * 50)
    
    for i, prompt_name in enumerate(prompt_names):
        # If we have output from previous step, add it to accumulated params
        if last_result and last_result.get("output"):
            prev_prompt = prompt_names[i - 1]
            output_key = PROMPTS[prev_prompt]["output_key"]
            accumulated_params[output_key] = last_result["output"]
            print(f"\n📤 Passing {prev_prompt} output as '{output_key}'")
        
        # Filter to only params this prompt accepts
        prompt_params = filter_params_for_prompt(prompt_name, accumulated_params)
        last_result = run_prompt(prompt_name, prompt_params)
    
    print("\n" + "=" * 50)
    print("✅ Chain complete!")
    return last_result

def run_scenario(scenario_name: str) -> Dict[str, Any]:
    """Run a predefined scenario"""
    if scenario_name not in SCENARIOS:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"   Available: {', '.join(SCENARIOS.keys())}")
        sys.exit(1)
    
    scenario = SCENARIOS[scenario_name]
    print(f"\n📋 Scenario: {scenario_name}")
    print(f"   {scenario['description']}")
    
    # Build params: start with default test data if enabled, then overlay base_params
    params = {}
    if scenario.get("use_default_test_data"):
        params = dict(DEFAULT_TEST_DATA)
        print(f"   Using default test data")
    
    # Overlay any scenario-specific base_params
    params.update(scenario.get("base_params", {}))
    
    return run_chain(scenario["chain"], params)

def show_diff(prompt_name: str):
    """Show diff between last two runs"""
    results = get_last_n_results(prompt_name, 2)
    
    if len(results) < 2:
        print(f"❌ Need at least 2 results to compare. Found: {len(results)}")
        return
    
    print(f"\n📊 Comparing last 2 runs of '{prompt_name}':")
    print("=" * 50)
    
    for i, r in enumerate(results):
        label = "LATEST" if i == 0 else "PREVIOUS"
        print(f"\n[{label}] {r['timestamp']}")
        print("-" * 30)
        # Show first 500 chars of output
        output = r.get("output", "")[:500]
        print(output + ("..." if len(r.get("output", "")) > 500 else ""))
    
    print("\n💡 Tip: Check full outputs in test_results/*.md files")
    print("💡 Tip: Use 'git diff' on prompt files to see what changed")

def list_results():
    """List all saved results"""
    if not RESULTS_DIR.exists():
        print("No results yet. Run some tests first!")
        return
    
    print("\n📁 Saved Results:")
    print("=" * 50)
    
    for prompt_name in PROMPTS.keys():
        files = sorted(RESULTS_DIR.glob(f"{prompt_name}_*.json"), reverse=True)
        if files:
            print(f"\n{prompt_name}:")
            for f in files[:3]:  # Show last 3
                print(f"  - {f.name}")
            if len(files) > 3:
                print(f"  ... and {len(files) - 3} more")

# ============================================================================
# CLI
# ============================================================================

def print_help():
    print(__doc__)
    print("\nAvailable prompts:", ", ".join(PROMPTS.keys()))
    print("Available scenarios:", ", ".join(SCENARIOS.keys()))

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command == "run" and len(sys.argv) >= 3:
        run_prompt(sys.argv[2], use_defaults=True)
    
    elif command == "chain" and len(sys.argv) >= 4:
        run_chain(sys.argv[2:], DEFAULT_TEST_DATA)
    
    elif command == "scenario" and len(sys.argv) >= 3:
        run_scenario(sys.argv[2])
    
    elif command == "diff" and len(sys.argv) >= 3:
        show_diff(sys.argv[2])
    
    elif command == "list":
        list_results()
    
    elif command == "help":
        print_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

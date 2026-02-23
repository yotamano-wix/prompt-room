"""
Batch Preview Generator
=======================
Run multiple site generations with random prompt + image pairing, 2 at a time.
Results are saved per run and summarized in an HTML report table.

Setup:
  1. Create batch_config.json with user_prompts, reference_image_urls, and optional reference_image_folder.
  2. First time: run preview_automation.py --setup (and optionally open a second browser for worker 2:
     python batch_preview.py --setup-worker 1)
  3. Run: python batch_preview.py --count 10

  Or use a full config file (e.g. from Streamlit UI):
     python batch_preview.py --config batch_results/batch_YYYYMMDD_HHMMSS/run_config.json

Limitation: Only 2 generations run concurrently; each uses its own browser window
(.playwright-profile-batch-0 and .playwright-profile-batch-1).
"""

import csv
import json
import random
import sys
from pathlib import Path
from multiprocessing import Process, Queue

BATCH_CONFIG_PATH = Path("batch_config.json")
BATCH_RESULTS_DIR = Path("batch_results")


def load_batch_config():
    with open(BATCH_CONFIG_PATH, "r") as f:
        config = json.load(f)
    prompts = config.get("user_prompts", [])
    urls = list(config.get("reference_image_urls", []))
    # reference_image_folder: add hosted URLs for those images to reference_image_urls; local file:// not used for API
    return prompts, urls, config.get("max_concurrent", 2)


def worker(task_queue: Queue, result_queue: Queue, worker_id: int, batch_results_dir: Path, prompt_overrides: dict | None):
    """Run batch flows from the task queue. Each task is (run_id, user_prompt, reference_image_url, task_brand_book or None)."""
    while True:
        try:
            task = task_queue.get_nowait()
        except Exception:
            break
        if task is None:
            break
        run_id, user_prompt, reference_image_url, task_brand_book = task
        sys.path.insert(0, str(Path(__file__).parent))
        from preview_automation import run_single_batch_flow
        try:
            result = run_single_batch_flow(
                run_id, user_prompt, reference_image_url, worker_id, batch_results_dir,
                prompt_overrides=prompt_overrides,
                manual_brand_book=task_brand_book,
            )
        except Exception as e:
            result = {"run_id": run_id, "error": str(e), "user_prompt": user_prompt, "reference_image_url": reference_image_url}
        result_queue.put(result)


def generate_report(results: list, output_path: Path):
    """Generate HTML table report."""
    rows = []
    for r in results:
        run_id = r.get("run_id", "")
        prompt = (r.get("user_prompt") or "")[:200] + ("..." if len(r.get("user_prompt") or "") > 200 else "")
        ref_url = (r.get("reference_image_url") or "")[:80] + ("..." if len(r.get("reference_image_url") or "") > 80 else "")
        publish_url = r.get("publish_url") or ""
        screenshot_path = r.get("screenshot_path") or ""
        brand_preview = (r.get("brand_book_preview") or "")[:300].replace("<", "&lt;").replace(">", "&gt;")
        error = r.get("error") or ""

        screenshot_cell = ""
        if screenshot_path and Path(screenshot_path).exists():
            try:
                rel = Path(screenshot_path).relative_to(output_path.parent)
            except ValueError:
                rel = Path(screenshot_path)
            screenshot_cell = f'<a href="{rel}"><img src="{rel}" alt="screenshot" style="max-width:200px;max-height:150px;object-fit:contain;" /></a>'
        else:
            screenshot_cell = "—"

        rows.append(f"""
        <tr>
            <td>{run_id}</td>
            <td><small>{prompt}</small></td>
            <td><small><a href="{ref_url}">ref</a></small></td>
            <td><small>{brand_preview}</small></td>
            <td><a href="{publish_url}">link</a></td>
            <td>{screenshot_cell}</td>
            <td><small>{error}</small></td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Batch Preview Report</title>
    <style>
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background: #f5f5f5; }}
        small {{ font-size: 0.85em; color: #555; }}
    </style>
</head>
<body>
    <h1>Batch Preview Report</h1>
    <p>Total runs: {len(results)}</p>
    <table>
        <thead>
            <tr>
                <th>Run</th>
                <th>User prompt</th>
                <th>Ref image</th>
                <th>Brand book (preview)</th>
                <th>Publish URL</th>
                <th>Screenshot</th>
                <th>Error</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")
    print(f"\n📄 Report: {output_path.absolute()}")


def generate_csv(results: list, prompt_overrides: dict | None, output_path: Path) -> None:
    """Write results to CSV with columns per plan."""
    if not results:
        output_path.write_text("", encoding="utf-8")
        return
    overrides = prompt_overrides or {}
    rows = []
    for r in results:
        screenshot_path = r.get("screenshot_path") or ""
        if screenshot_path and output_path.parent:
            try:
                screenshot_path = str(Path(screenshot_path).relative_to(output_path.parent))
            except ValueError:
                pass
        rows.append({
            "Run #": r.get("run_id", ""),
            "User Request": (r.get("user_prompt") or ""),
            "Reference Image URL": (r.get("reference_image_url") or ""),
            "Publish URL": (r.get("publish_url") or ""),
            "Editor URL": (r.get("editor_url") or ""),
            "Screenshot": screenshot_path,
            "Brand Book Preview": (r.get("brand_book_preview") or "")[:300],
            "Architect Prompt ID": overrides.get("architectPromptId", ""),
            "Typography Prompt ID": overrides.get("typographyPromptId", ""),
            "Copier Prompt ID": overrides.get("copierPromptId", ""),
            "Designer Prompt ID": overrides.get("designerPromptId", ""),
            "Status": "error" if r.get("error") else "success",
            "Error": (r.get("error") or ""),
        })
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n📄 CSV: {output_path.absolute()}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch site generation with random prompt + image")
    parser.add_argument("--count", type=int, default=4, help="Number of sites to generate")
    parser.add_argument("--concurrency", type=int, default=2, help="Max concurrent runs (default 2)")
    parser.add_argument("--setup-worker", type=int, default=None, help="Open browser for worker N (0 or 1) to log in")
    parser.add_argument("--config", type=str, default=None, help="Path to JSON config file (output_dir, tasks, concurrency, prompt_overrides, manual_brand_book)")
    args = parser.parse_args()

    if args.setup_worker is not None:
        if args.setup_worker not in (0, 1):
            print("--setup-worker must be 0 or 1")
            sys.exit(1)
        from preview_automation import launch_browser, setup_profile
        import preview_automation
        profile_dir = Path(f".playwright-profile-batch-{args.setup_worker}")
        preview_automation.PROFILE_DIR = profile_dir
        print(f"Opening browser for worker {args.setup_worker} (profile: {profile_dir})")
        setup_profile()
        return

    # --- Config file mode (e.g. from Streamlit) ---
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Config file not found: {config_path}")
            sys.exit(1)
        with open(config_path, "r") as f:
            run_config = json.load(f)
        output_dir = Path(run_config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        tasks_config = run_config["tasks"]
        concurrency = min(int(run_config.get("concurrency", 2)), 4)
        prompt_overrides = run_config.get("prompt_overrides") or {}
        tasks = []
        for i, t in enumerate(tasks_config):
            run_id = t.get("run_id") or f"run_{i+1:03d}"
            bb = t.get("brand_book") or None
            if isinstance(bb, str) and not bb.strip():
                bb = None
            tasks.append((run_id, t["user_prompt"], t["reference_image_url"], bb))
        total = len(tasks)
        print(f"\n🔄 Batch (config): {total} runs, {concurrency} at a time")
        print(f"   Results: {output_dir}/")

        task_queue = Queue()
        result_queue = Queue()
        for t in tasks:
            task_queue.put(t)
        for _ in range(concurrency):
            task_queue.put(None)

        workers = [
            Process(
                target=worker,
                args=(task_queue, result_queue, i, output_dir, prompt_overrides),
            )
            for i in range(concurrency)
        ]
        for w in workers:
            w.start()

        results = []
        while len(results) < total:
            r = result_queue.get()
            results.append(r)
            results_sorted = sorted(results, key=lambda x: x.get("run_id", ""))
            progress_path = output_dir / "progress.json"
            progress_path.write_text(json.dumps({
                "completed": len(results),
                "total": total,
                "runs": results_sorted,
            }, indent=2))
            (output_dir / "results.json").write_text(json.dumps(results_sorted, indent=2))

        for w in workers:
            w.join()

        results = sorted(results, key=lambda r: r.get("run_id", ""))
        report_path = output_dir / "report.html"
        generate_report(results, report_path)
        (output_dir / "results.json").write_text(json.dumps(results, indent=2))
        generate_csv(results, prompt_overrides, output_dir / "results.csv")
        print(f"   Done. Open {report_path} in a browser to review.")
        return

    # --- Legacy CLI mode ---
    prompts, urls, max_concurrent = load_batch_config()
    if not prompts:
        print("Add user_prompts to batch_config.json")
        sys.exit(1)
    if not urls:
        print("Add reference_image_urls (and/or reference_image_folder) to batch_config.json")
        sys.exit(1)

    concurrency = min(args.concurrency, max_concurrent, 2)
    count = args.count
    tasks = []
    for i in range(count):
        run_id = f"run_{i+1:03d}"
        user_prompt = random.choice(prompts)
        reference_image_url = random.choice(urls)
        tasks.append((run_id, user_prompt, reference_image_url, None))

    BATCH_RESULTS_DIR.mkdir(exist_ok=True)
    (BATCH_RESULTS_DIR / "batch_runs.json").write_text(json.dumps([{"run_id": t[0], "user_prompt": t[1], "reference_image_url": t[2]} for t in tasks], indent=2))

    print(f"\n🔄 Batch: {count} runs, {concurrency} at a time")
    print(f"   Prompts: {len(prompts)}, Images: {len(urls)}")
    print(f"   Results: {BATCH_RESULTS_DIR}/")

    task_queue = Queue()
    result_queue = Queue()
    for t in tasks:
        task_queue.put(t)
    for _ in range(concurrency):
        task_queue.put(None)

    workers = [
        Process(target=worker, args=(task_queue, result_queue, i, BATCH_RESULTS_DIR, None))
        for i in range(concurrency)
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    results = []
    while not result_queue.empty():
        results.append(result_queue.get_nowait())
    results.sort(key=lambda r: r.get("run_id", ""))

    report_path = BATCH_RESULTS_DIR / "report.html"
    generate_report(results, report_path)
    (BATCH_RESULTS_DIR / "results.json").write_text(json.dumps(results, indent=2))
    generate_csv(results, None, BATCH_RESULTS_DIR / "results.csv")
    print(f"   Done. Open {report_path} in a browser to review.")


if __name__ == "__main__":
    main()

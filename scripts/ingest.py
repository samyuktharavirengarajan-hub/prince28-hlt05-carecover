"""Start and monitor CareCover document ingestion."""

import argparse
import time

import httpx

from carecover.config import get_settings


def main():
    parser = argparse.ArgumentParser(description="Start or monitor CareCover document ingestion.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="CareCover API base URL",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--source", default="")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--every", type=float, default=3.0)

    args = parser.parse_args()

    if not 1 <= args.limit <= 2000:
        parser.error("--limit must be between 1 and 2000")
    if args.every <= 0:
        parser.error("--every must be greater than 0")

    settings = get_settings()
    headers = {}
    if settings.admin_token:
        headers["X-Admin-Token"] = settings.admin_token

    base_url = args.url.rstrip("/")

    payload = {
        "limit": args.limit,
        "source": args.source,
        "retry_failed": args.retry_failed,
    }

    with httpx.Client(timeout=30.0, headers=headers) as client:
        response = client.post(
            f"{base_url}/v1/ingest",
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

        job_id = result.get("job_id")

        if not job_id:
            print(result.get("detail", "No documents queued."))
            return

        print(f"Job ID: {job_id}")
        print(f"Queued: {result['queued']}")
        print(f"Progress URL: {base_url}/v1/ingest/{job_id}")

        if not args.watch:
            return

        print("\nWatching ingestion progress...")

        while True:
            response = client.get(f"{base_url}/v1/ingest/{job_id}")
            response.raise_for_status()
            progress = response.json()

            counts = progress["counts"]
            print(
                f"Status: {progress['status']} | "
                f"Queued: {counts['queued']} | "
                f"Running: {counts['running']} | "
                f"Done: {counts['done']} | "
                f"Skipped: {counts['skipped']} | "
                f"Failed: {counts['failed']} | "
                f"Pages: {progress['pages']} | "
                f"Elapsed: {progress['seconds']}s"
            )

            if progress["status"] == "finished":
                if progress["dead_letter"]:
                    print("\nFailed items:")
                    for item in progress["dead_letter"]:
                        print(f"- Item {item['item']}: {item['error'] or 'No error detail'}")
                break

            time.sleep(args.every)


if __name__ == "__main__":
    main()

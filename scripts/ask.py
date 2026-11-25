"""Ask CareCover a question through its streaming chat API."""

import argparse
import json

import httpx


def main():
    parser = argparse.ArgumentParser(description="Ask the CareCover assistant.")
    parser.add_argument("question", nargs="?", help="Your question for CareCover")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="CareCover API base URL",
    )
    args = parser.parse_args()

    question = args.question or input("You: ").strip()
    if not question:
        parser.error("Please provide a question.")

    url = f"{args.url.rstrip('/')}/v1/chat"

    print("\nCareCover: ", end="", flush=True)

    metadata = None

    with (
        httpx.Client(timeout=120.0) as client,
        client.stream(
            "POST",
            url,
            json={"message": question},
        ) as response,
    ):
        response.raise_for_status()

        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue

            payload = json.loads(line[6:])

            if payload["type"] == "delta":
                print(payload["text"], end="", flush=True)
            elif payload["type"] == "done":
                metadata = payload
            elif payload["type"] == "error":
                raise RuntimeError(payload["message"])

    print("\n")

    if metadata:
        print(f"Provider: {metadata['provider']}")
        print(f"Model: {metadata['model']}")
        print(f"Input tokens: {metadata['tokens_in']}")
        print(f"Output tokens: {metadata['tokens_out']}")
        print(f"Latency: {metadata['latency_ms']} ms")
        print(f"Fallback used: {metadata['fallback_used']}")
        print(f"Estimated cost: INR {metadata['cost_inr']:.6f}")


if __name__ == "__main__":
    main()

import asyncio

import httpx

URLS = [
    "https://www.cmchistn.com/package/PMJAY_Packages.pdf",
    "https://www.cmchistn.com/circular/PMAM_Manual_version%202.0.pdf",
]


async def main():
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
    ) as client:
        for url in URLS:
            print(f"\nChecking: {url}")

            try:
                response = await client.get(url)

                print("Status:", response.status_code)
                print("Final URL:", response.url)
                print("Content-Type:", response.headers.get("content-type"))
                print("Content-Length:", response.headers.get("content-length"))
                print("First 30 bytes:", response.content[:30])

            except httpx.HTTPError as error:
                print("Request failed:", error)


if __name__ == "__main__":
    asyncio.run(main())

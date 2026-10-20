import argparse
import asyncio
import time
import uuid
import httpx

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--concurrency", type=int, default=25)
    p.add_argument("--url", default="http://localhost:8000")
    args = p.parse_args()
    sem = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(timeout=30) as client:
        async def one(i):
            async with sem:
                try:
                    r = await client.post(args.url + "/payments", headers={"Idempotency-Key": str(uuid.uuid4())}, json={"user_id": f"u{i}", "merchant_id": "m1", "amount": 1000+i})
                    return r.status_code
                except httpx.HTTPError:
                    return 0
        start = time.monotonic()
        codes = await asyncio.gather(*(one(i) for i in range(args.count)))
    elapsed = time.monotonic()-start
    print({"requests":len(codes),"success":codes.count(200),"errors":len(codes)-codes.count(200),"seconds":round(elapsed,2),"requests_per_second":round(len(codes)/elapsed,1)})
asyncio.run(main())

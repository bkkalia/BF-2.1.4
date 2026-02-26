import asyncio
import sys

try:
    import websockets
except Exception:
    print("MISSING_WEBSOCKETS")
    sys.exit(2)

async def main():
    uri = "ws://localhost:8002/_event"
    try:
        async with websockets.connect(uri, open_timeout=5) as ws:
            print("CONNECTED")
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                print("RECV:", msg)
            except asyncio.TimeoutError:
                print("NO_MESSAGE")
    except Exception as e:
        print("ERROR:", repr(e))

if __name__ == '__main__':
    asyncio.run(main())

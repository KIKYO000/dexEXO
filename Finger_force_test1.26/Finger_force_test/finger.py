import asyncio
import json
from bleak import BleakClient

DEVICE_ADDRESSES = [
    "F0:FD:45:02:85:B3",  # ??1 MAC??
    "F0:FD:45:02:67:3B",  # ??2 MAC??
]
TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # ??????? UUID
RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # ??????? UUID

def parse_and_print(data: bytes):
    text = data.decode("utf-8", errors="ignore").strip()
    if not text:
        return
    try:
        obj = json.loads(text)
        print(json.dumps(obj, ensure_ascii=False))
    except json.JSONDecodeError:
        # ????/????????????? JSON?????????
        print(text)

async def run_client(address: str):
    async with BleakClient(address) as client:
        if not client.is_connected:
            print(f"????: {address}")
            return
        print(f"???: {address}")

        def notification_handler(_, data: bytearray):
            parse_and_print(bytes(data))

        await client.start_notify(RX_CHAR_UUID, notification_handler)
        print("???????? Ctrl+C ??")
        while True:
            await asyncio.sleep(1)

async def main():
    for addr in DEVICE_ADDRESSES:
        try:
            await run_client(addr)
            break
        except Exception as e:
            print(f"?? {addr} ??: {e}")

if __name__ == "__main__":
    asyncio.run(main())
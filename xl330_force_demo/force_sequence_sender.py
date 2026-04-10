#!/usr/bin/env python3
"""
Send a sequence of force commands to xl330_force_demo.py via its WiFi server (TCP 8888).
Forces: 5 -> 30 N in 5 N steps, 10 s apart.
"""
import socket
import time
from typing import Iterable

HOST = "127.0.0.1"  # same machine running xl330_force_demo.py
PORT = 8888         # default port used by the demo WiFi server
FORCE_SEQUENCE = [5, 10, 15, 20, 25, 30]
INTERVAL_SEC = 10

def send_commands(forces: Iterable[int]) -> None:
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        def send(cmd: str):
            data = (cmd.strip() + "\n").encode()
            s.sendall(data)
            print(f"[SEND] {cmd.strip()}")
            try:
                s.settimeout(1.0)
                resp = s.recv(1024)
                if resp:
                    print(f"[RECV] {resp.decode().strip()}")
            except socket.timeout:
                pass

        # 先切到纯电流模式
        send("IMODE")
        time.sleep(1.0)

        for f in forces:
            send(f"N:{f}")
            time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    print(f"Connecting to {HOST}:{PORT} ...")
    send_commands(FORCE_SEQUENCE)
    print("Done.")

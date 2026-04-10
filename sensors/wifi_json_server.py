#!/usr/bin/env python3
"""
Simple TCP JSON receiver for testing gatt_blu_251202.py WiFi sender.
Listens on port 9999 (configurable) and prints each incoming JSON object (one per line) prettily.

Usage:
  python sensors/wifi_json_server.py --host 0.0.0.0 --port 9999

You can run this on your Ubuntu host (WIFI_SERVER_IP in the BLE script) and it will show received payloads.
"""
import argparse
import socket
import json
import threading
import datetime


def handle_client(conn, addr):
    print(f"[+] Connection from {addr}")
    with conn:
        buffer = b""
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                # split by newline (each JSON payload is one line)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode('utf-8'))
                        ts = datetime.datetime.now().isoformat()
                        print(f"[{ts}] Received JSON from {addr}:")
                        print(json.dumps(obj, indent=2, ensure_ascii=False))
                    except Exception as e:
                        print(f"[!] Failed to parse JSON: {e}")
                        print(line)
            except Exception as e:
                print(f"Connection error {addr}: {e}")
                break
    print(f"[-] Disconnected {addr}")


def run_server(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    print(f"Listening on {host}:{port} ...")
    try:
        while True:
            conn, addr = sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("Shutting down server")
    finally:
        sock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=9999)
    args = parser.parse_args()
    run_server(args.host, args.port)

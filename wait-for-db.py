import socket
import time
import os

def wait_for_port(host, port):
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                print(f"Successfully connected to {host}:{port}")
                break
        except (socket.timeout, ConnectionRefusedError):
            print(f"Waiting for {host}:{port}...")
            time.sleep(1)

if __name__ == "__main__":
    wait_for_port("db", 5432)


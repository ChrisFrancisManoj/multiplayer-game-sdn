# server.py - Game server
# TCP port 5000: login (JOIN) and chat (CHAT) -> needs reliability
# UDP port 6000: player position updates -> needs speed, echoed back to measure RTT
import socket
import threading

HOST = "0.0.0.0"
TCP_PORT = 5000
UDP_PORT = 6000


def handle_tcp_client(conn, addr):
    print(f"[TCP] player connected: {addr}", flush=True)
    f = conn.makefile("rw")
    try:
        for line in f:
            line = line.strip()
            if line.startswith("JOIN"):
                print(f"[TCP] {line}", flush=True)
                f.write("WELCOME\n")
                f.flush()
            elif line.startswith("CHAT"):
                print(f"[TCP] {line}", flush=True)
                f.write("OK\n")
                f.flush()
    except Exception:
        pass
    finally:
        conn.close()
        print(f"[TCP] player left: {addr}", flush=True)


def tcp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, TCP_PORT))
    s.listen(10)
    print(f"[TCP] listening on port {TCP_PORT}", flush=True)
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()


def udp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, UDP_PORT))
    print(f"[UDP] listening on port {UDP_PORT}", flush=True)
    while True:
        data, addr = s.recvfrom(2048)
        s.sendto(data, addr)  # echo the packet back so the client can measure RTT


if __name__ == "__main__":
    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_server, daemon=True).start()
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")

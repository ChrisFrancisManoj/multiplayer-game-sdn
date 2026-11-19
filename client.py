# client.py - Game player
# TCP: sends JOIN and CHAT messages every second (reliable)
# UDP: sends position packets 20 times/sec, server echoes them back
# We use the echo to measure RTT (delay), jitter and packet loss
import socket
import threading
import time
import json
import argparse
import os
import random

UDP_PORT = 6000
TCP_PORT = 5000


def tcp_worker(server, pid, stop):
    try:
        s = socket.create_connection((server, TCP_PORT), timeout=5)
        f = s.makefile("rw")
        f.write(f"JOIN {pid}\n")
        f.flush()
        print("[TCP] server says:", f.readline().strip(), flush=True)
        n = 0
        while not stop.is_set():
            n += 1
            f.write(f"CHAT {pid} hello {n}\n")
            f.flush()
            f.readline()
            stop.wait(1)
        s.close()
    except Exception as e:
        print("[TCP] error:", e, flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="127.0.0.1")
    p.add_argument("--id", default="p1")
    p.add_argument("--duration", type=float, default=10)
    p.add_argument("--rate", type=float, default=20)
    p.add_argument("--log", default="")  # file prefix for the CSV, e.g. logs/test_h1
    a = p.parse_args()

    stop = threading.Event()
    threading.Thread(target=tcp_worker, args=(a.server, a.id, stop), daemon=True).start()

    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.settimeout(0.005)
    sent = 0
    rtts = {}  # seq -> rtt in ms
    interval = 1.0 / a.rate
    start = time.time()
    next_send = start

    def try_receive():
        try:
            data, _ = u.recvfrom(2048)
            r = json.loads(data.decode())
            rtts[r["seq"]] = (time.time() - r["ts"]) * 1000
        except (socket.timeout, ValueError, KeyError):
            pass

    while time.time() - start < a.duration:
        if time.time() >= next_send:
            pkt = {"player_id": a.id, "seq": sent, "ts": time.time(),
                   "x": random.randint(0, 100), "y": random.randint(0, 100)}
            u.sendto(json.dumps(pkt).encode(), (a.server, UDP_PORT))
            sent += 1
            next_send += interval
        try_receive()

    # wait 1 more second for late replies
    end_wait = time.time() + 1
    while time.time() < end_wait:
        try_receive()
    stop.set()

    got = len(rtts)
    loss = 100.0 * (sent - got) / sent if sent else 0
    vals = [rtts[k] for k in sorted(rtts)]
    avg = sum(vals) / len(vals) if vals else 0
    mx = max(vals) if vals else 0
    diffs = [abs(vals[i] - vals[i - 1]) for i in range(1, len(vals))]
    jitter = sum(diffs) / len(diffs) if diffs else 0

    print(f"RESULT player={a.id} sent={sent} received={got} loss={loss:.1f}% "
          f"avg_rtt={avg:.2f}ms max_rtt={mx:.2f}ms jitter={jitter:.2f}ms", flush=True)

    if a.log:
        os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
        with open(a.log + ".csv", "w") as f:
            f.write("seq,rtt_ms\n")
            for i in range(sent):
                f.write(f"{i},{rtts[i]:.3f}\n" if i in rtts else f"{i},\n")


if __name__ == "__main__":
    main()

# plot.py - makes 2 graphs from the test logs
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

tests = [("sdn_baseline", "T1 Baseline"),
         ("sdn_noqos", "T2 Congestion, no QoS"),
         ("sdn_qos", "T3 Congestion + QoS")]
RATE = 20.0  # packets per second


def load(tag, host):
    xs, ys = [], []
    with open(f"logs/{tag}_{host}.csv") as f:
        for row in csv.DictReader(f):
            if row["rtt_ms"]:
                xs.append(int(row["seq"]) / RATE)
                ys.append(float(row["rtt_ms"]))
    return xs, ys


# Graph 1: RTT over time for player h1
plt.figure(figsize=(9, 5))
for tag, label in tests:
    x, y = load(tag, "h1")
    plt.plot(x, y, label=label)
plt.yscale("log")
plt.xlabel("Time (seconds)")
plt.ylabel("Round-trip time (ms, log scale)")
plt.title("Game packet delay over time (player h1)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("sdn_graph1_rtt_over_time.png", dpi=150)

# Graph 2: average RTT per test (average of h1, h2, h3)
avgs = []
for tag, label in tests:
    vals = []
    for h in ("h1", "h2", "h3"):
        vals += load(tag, h)[1]
    avgs.append(sum(vals) / len(vals))

plt.figure(figsize=(8, 5))
bars = plt.bar([t[1] for t in tests], avgs, color=["#4caf50", "#e53935", "#1e88e5"])
plt.yscale("log")
plt.ylabel("Average RTT (ms, log scale)")
plt.title("Average game delay per scenario")
for b, v in zip(bars, avgs):
    plt.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f} ms", ha="center", va="bottom")
plt.tight_layout()
plt.savefig("sdn_graph2_avg_rtt.png", dpi=150)
print("Saved sdn_graph1_rtt_over_time.png and sdn_graph2_avg_rtt.png")

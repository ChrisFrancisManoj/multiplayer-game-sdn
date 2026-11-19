# Multiplayer Game Communication Network (TCP/UDP + Mininet + Ryu SDN)

A small multiplayer game system where players send real-time state over UDP and
reliable events (login, chat) over TCP. It runs on a Mininet network with an
Open vSwitch switch, and a Ryu SDN controller prioritizes game traffic when the
network is congested.

## Architecture

- h1, h2, h3: players (`client.py`)
- h4: game server (`server.py`): TCP 5000 (JOIN, CHAT), UDP 6000 (position echo)
- h5: background traffic generator (iperf3, 20 Mbps UDP)
- s1: Open vSwitch (OpenFlow 1.3), link to h4 limited to 10 Mbps with HTB queues
- c0: Ryu controller (`game_controller.py`)

With QoS on, the controller sends game traffic (UDP 6000, TCP 5000) to the
priority queue (queue 1) and everything else going to the server to the bulk
queue (queue 2).

## Files

| File | Purpose |
|---|---|
| `server.py` | Game server (TCP + UDP, threaded) |
| `client.py` | Player: 20 UDP packets/s, TCP chat, reports loss/RTT/jitter |
| `topo.py` | Mininet topology, queues, automatic test runner |
| `game_controller.py` | Ryu app: learning switch + QoS queue selection |
| `plot.py`, `plot_sdn.py` | Graph scripts |
| `logs/` | Per-run results and per-packet CSVs |

## Setup (Ubuntu VM)

```bash
sudo apt update && sudo apt install mininet openvswitch-switch iperf3 python3-matplotlib -y
sudo systemctl start openvswitch-switch
pip3 install --user --break-system-packages uv
~/.local/bin/uv venv --python 3.9 ryu-env
~/.local/bin/uv pip install --python ryu-env/bin/python "setuptools<58" wheel pbr
~/.local/bin/uv pip install --python ryu-env/bin/python --no-build-isolation ryu eventlet==0.30.2
```

Ryu needs an older Python, so it runs in its own Python 3.9 environment.

## Run

Sockets only (no Mininet):

```bash
python3 server.py
python3 client.py --id test --duration 5     # in a second terminal
```

Full experiment. Use two terminals. Do not run `sudo mn -c` while the controller
is running, because it stops Ryu.

```bash
# Terminal 1, controller (QoS off)
sudo mn -c && ryu-env/bin/ryu-manager game_controller.py
# Terminal 2
sudo python3 topo.py --auto --tag sdn_baseline
sudo python3 topo.py --auto --tag sdn_noqos --congest

# Terminal 1: stop with Ctrl+C, then restart with QoS on
sudo mn -c && QOS=1 ryu-env/bin/ryu-manager game_controller.py
# Terminal 2
sudo python3 topo.py --auto --tag sdn_qos --congest

# Graphs
python3 plot_sdn.py
```

Extra options in `topo.py`: `--noctl` (no controller, standalone switch) and
`--ovsqos` (install the same QoS rules by hand with ovs-ofctl).

## Results (3 players, 20 packets/s, 20 s per run)

| Test | Loss | Avg RTT | Jitter |
|---|---|---|---|
| Baseline (no congestion) | 0% | ~1.2 ms | ~0.5 ms |
| Congestion, QoS off | 0% | ~87 ms | ~14.4 ms |
| Congestion, QoS on (Ryu) | 0% | ~1.2 ms | ~0.6 ms |

Congestion mainly raised delay and jitter, not packet loss, because the switch
queue is deep. Giving game traffic its own queue brought delay back to baseline.

## Limitations

Each scenario was run once with 3 players. Scaling tests and link-failure tests
are not included.

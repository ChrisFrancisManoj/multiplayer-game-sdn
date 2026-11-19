# topo.py - Mininet network for the multiplayer game project
# h1,h2,h3 = players | h4 = game server | h5 = background traffic
# s1 = OpenFlow switch | c0 = remote Ryu controller
# The link s1 -> h4 is limited to 10 Mbps so congestion really happens.
import os
import time
import argparse
import subprocess
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

BASE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(BASE, "logs")
SERVER_IP = "10.0.0.4"


def setup_queues():
    # 10 Mbps bottleneck on s1-eth4 (port facing the server) with 3 queues:
    # queue 0 = default, queue 1 = game (min 6 Mbps), queue 2 = bulk
    cmd = (
        "ovs-vsctl -- set port s1-eth4 qos=@q "
        "-- --id=@q create qos type=linux-htb other-config:max-rate=10000000 "
        "queues:0=@q0 queues:1=@q1 queues:2=@q2 "
        "-- --id=@q0 create queue other-config:min-rate=1000000 other-config:max-rate=10000000 "
        "-- --id=@q1 create queue other-config:min-rate=6000000 other-config:max-rate=10000000 "
        "-- --id=@q2 create queue other-config:min-rate=1000000 other-config:max-rate=10000000"
    )
    subprocess.run(cmd, shell=True, check=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--auto", action="store_true", help="run the test automatically")
    p.add_argument("--tag", default="test", help="name for this run, e.g. baseline")
    p.add_argument("--congest", action="store_true", help="h5 floods the server")
    p.add_argument("--duration", type=int, default=20)
    p.add_argument("--noctl", action="store_true", help="no controller: switch acts as a normal learning switch")
    p.add_argument("--ovsqos", action="store_true", help="install QoS OpenFlow rules by hand")
    a = p.parse_args()

    os.makedirs(LOGS, exist_ok=True)
    setLogLevel("info")

    net = Mininet(controller=None, switch=OVSSwitch, autoSetMacs=True)
    if a.noctl:
        s1 = net.addSwitch("s1", protocols="OpenFlow13", failMode="standalone")
    else:
        c0 = net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
        s1 = net.addSwitch("s1", protocols="OpenFlow13")
    hosts = [net.addHost(f"h{i}", ip=f"10.0.0.{i}/24") for i in range(1, 6)]
    for h in hosts:  # added in order, so h4 is on switch port 4
        net.addLink(h, s1)

    net.start()
    setup_queues()
    time.sleep(3)
    net.pingAll()  # lets the controller learn all hosts
    if a.ovsqos:
        rules = [
            "priority=100,udp,tp_dst=6000,actions=set_queue:1,output:4",
            "priority=100,tcp,tp_dst=5000,actions=set_queue:1,output:4",
            "priority=50,ip,nw_dst=10.0.0.4,actions=set_queue:2,output:4",
        ]
        for r in rules:
            subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "add-flow", "s1", r])
        print("QoS rules installed:")
        subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"])

    h1, h2, h3, h4, h5 = hosts

    if not a.auto:
        print("\nManual mode. Try: h4 python3 server.py &")
        CLI(net)
        net.stop()
        return

    # start the game server on h4
    h4.cmd(f"python3 {BASE}/server.py > {LOGS}/server.log 2>&1 &")
    time.sleep(2)

    # optional congestion: h5 floods the server with 20 Mbps UDP
    if a.congest:
        h4.cmd("iperf3 -s -D")
        time.sleep(1)
        h5.cmd(f"iperf3 -c {SERVER_IP} -u -b 20M -t {a.duration + 8} > {LOGS}/{a.tag}_iperf.txt 2>&1 &")
        time.sleep(3)

    # start the 3 players
    for h in (h1, h2, h3):
        h.cmd(f"python3 {BASE}/client.py --server {SERVER_IP} --id {h.name} "
              f"--duration {a.duration} --log {LOGS}/{a.tag}_{h.name} "
              f"> {LOGS}/{a.tag}_{h.name}.txt 2>&1 &")

    print(f"\nRunning test '{a.tag}' for about {a.duration + 5} seconds...")
    time.sleep(a.duration + 5)

    print("\n===== RESULTS =====")
    for h in (h1, h2, h3):
        path = f"{LOGS}/{a.tag}_{h.name}.txt"
        found = False
        if os.path.exists(path):
            for line in open(path):
                if line.startswith("RESULT"):
                    print(line.strip())
                    found = True
        if not found:
            print(f"{h.name}: no RESULT found, check {path}")

    h4.cmd("pkill -f server.py")
    h4.cmd("pkill iperf3")
    net.stop()


if __name__ == "__main__":
    main()

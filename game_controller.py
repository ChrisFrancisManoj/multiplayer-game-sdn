# game_controller.py - Ryu SDN controller (OpenFlow 1.3)
# Normal mode: acts as a learning switch
# QOS=1 mode: game traffic (UDP 6000, TCP 5000) -> priority queue 1
#             everything else going to the server -> bulk queue 2
import os
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, tcp, udp, ether_types

SERVER_PORT_NO = 4   # switch port connected to h4 (the game server)
QOS = os.environ.get("QOS") == "1"


class GameController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.logger.info("QoS mode: %s", "ON" if QOS else "OFF")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        # table-miss rule: send unknown packets to the controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

    def add_flow(self, dp, priority, match, actions, idle=0):
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match,
                                instructions=inst, idle_timeout=idle)
        dp.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst, src = eth.dst, eth.src
        table = self.mac_to_port.setdefault(dp.id, {})
        table[src] = in_port                      # learn where src lives
        out_port = table.get(dst, ofp.OFPP_FLOOD)  # known dst? else flood
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofp.OFPP_FLOOD:
            fields = dict(in_port=in_port, eth_dst=dst, eth_src=src)
            ip = pkt.get_protocol(ipv4.ipv4)
            if ip:
                fields.update(eth_type=0x0800, ipv4_src=ip.src,
                              ipv4_dst=ip.dst, ip_proto=ip.proto)
                t = pkt.get_protocol(tcp.tcp)
                u = pkt.get_protocol(udp.udp)
                if t:
                    fields.update(tcp_dst=t.dst_port)
                elif u:
                    fields.update(udp_dst=u.dst_port)
                # QoS: pick a queue for traffic heading to the server
                if QOS and out_port == SERVER_PORT_NO:
                    is_game = (t and t.dst_port == 5000) or (u and u.dst_port == 6000)
                    queue = 1 if is_game else 2
                    actions = [parser.OFPActionSetQueue(queue),
                               parser.OFPActionOutput(out_port)]
                # only IP traffic gets a flow rule; ARP must not get a catch-all rule
                self.add_flow(dp, 1, parser.OFPMatch(**fields), actions, idle=30)

        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        dp.send_msg(out)

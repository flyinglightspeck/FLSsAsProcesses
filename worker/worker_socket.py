import socket
import pickle
import select
import struct
import numpy as np
from constants import Constants
from config import Config
from utils import logger


class WorkerSocket:
    def __init__(self):
        self.sock = None
        if Config.MULTICAST:
            self.create_multicast_socket()
        else:
            self.create_udp_socket()

    def create_udp_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(Constants.WORKER_ADDRESS)
        self.sock = sock

    def create_multicast_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        # ttl = struct.pack('b', 1)
        # sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        sock.bind(Constants.WORKER_ADDRESS)
        # add the socket to the multicast group on all interfaces.
        group = socket.inet_aton(Constants.MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.sock = sock

    def close(self):
        self.sock.close()

    def receive(self):
        data, _ = self.sock.recvfrom(1024)
        try:
            msg = pickle.loads(data)
            return msg, len(data)
        except pickle.UnpicklingError:
            return None, 0

    def broadcast(self, msg, retry=2):
        if Config.DROP_PROB_SENDER:
            if np.random.random() <= Config.DROP_PROB_SENDER:
                return 0

        data = pickle.dumps(msg)
        address = Constants.MULTICAST_GROUP_ADDRESS if Config.MULTICAST else Constants.BROADCAST_ADDRESS
        try:
            self.sock.sendto(data, address)
        except OSError:
            if retry:
                self.broadcast(msg, retry - 1)
        return len(data)

    def send_to_server(self, msg):
        data = pickle.dumps(msg)
        self.sock.sendto(data, Constants.SERVER_ADDRESS)
        return len(data)

    def is_ready(self):
        ready = select.select([self.sock], [], [], 1)
        return ready[0]

    def send_test_msgs(self):
        id = 1
        n = 5
        for i in range(n):
            self.broadcast((id, i))

        for i in range(2 * n):
            print(ws.receive())


if __name__ == '__main__':
    ws = WorkerSocket()
    ws.send_test_msgs()

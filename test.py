import struct
import sys
import socket
import pickle


class Constants:
    BROADCAST_ADDRESS = ("<broadcast>", 5000)
    WORKER_ADDRESS = ("", 5000)


class WorkerSocket:
    def __init__(self):
        self.sock = None
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(Constants.WORKER_ADDRESS)
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
        data = pickle.dumps(msg)
        try:
            self.sock.sendto(data, Constants.BROADCAST_ADDRESS)
        except OSError:
            if retry:
                self.broadcast(msg, retry - 1)
        return len(data)

    def send_test_msgs(self):
        id = 1
        n = 5
        for i in range(n):
            self.broadcast((id, i))

        for i in range(n):
            print(ws.receive())

        self.close()

    def send_multicast(self):
        message = 'very important data'
        multicast_group = ('224.3.29.71', 10000)

        # Create the datagram socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set a timeout so the socket does not block indefinitely when trying
        # to receive data.
        sock.settimeout(0.2)

        # Set the time-to-live for messages to 1 so they do not go past the
        # local network segment.
        ttl = struct.pack('b', 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

        try:
            # Send data to the multicast group
            sent = sock.sendto(pickle.dumps(message), multicast_group)

            # Look for responses from all recipients
            while True:
                try:
                    data, server = sock.recvfrom(1024)
                except socket.timeout:
                    break
                else:
                    print(pickle.loads(data), server)

        finally:
            sock.close()

    def receive_multicast(self):
        multicast_group = '224.3.29.71'
        server_address = ('', 10000)

        # Create the socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Bind to the server address
        sock.bind(server_address)

        # Tell the operating system to add the socket to the multicast group
        # on all interfaces.
        group = socket.inet_aton(multicast_group)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Receive/respond loop
        while True:
            data, address = sock.recvfrom(1024)
            print(len(data), address)
            sock.sendto(pickle.dumps('ack'), address)


if __name__ == '__main__':
    ws = WorkerSocket()

    if len(sys.argv) > 1:
        ws.receive_multicast()
    else:
        ws.send_multicast()

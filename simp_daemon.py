import socket
import sys
import threading
import time

from sock import SIMP_Socket


class SimpDaemon:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.daemon_port = 7777
        self.client_port = 7778
        self.daemon_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # This is used to store the client's address, and username
        self.client_address = None
        self.client_username = None
        # Value is true if a client is connected
        self.client_connected = False
        # This stores the IP address of the other daemon that is connected
        self.other_daemon_ip = None
        # These are necessary for the stop and wait which is only used for the chat messages
        self.message_sent = False
        self.ack_received = False
        # The value of this is true if the other daemon is connected
        self.other_daemon_connected = False
        # This is used to indicate if there is a pending request before the client connects
        self.pending_request = False
        self.pending_request_data = None
        # This is used to indicate if the client sent a fin to close the connection, and the daemon is waiting for the ack
        self.fin_sent = False
        # This is used to store the messages that are sent by the client, but not yet acknowledged by the other daemon
        self.message_buffer = []
        # This is used to store the value of the client's response to the pending request
        self.accepted = None
        # These are the control types for the communication between the client and the daemon
        self.controlTypes = {
            b"\x00": "connect",
            b"\x01": "chat",
            b"\x02": "error",
            b"\x03": "quit",
            b"\x04": "connreq",
            b"\x05": "waitorstart",
            b'\x06': 'connestab',
            b'\x09': 'yesno',
            b'\x07': 'reask'
        }
        self.start()

    def start(self):
        self.daemon_socket.bind((self.ip_address, self.daemon_port))
        print(f"Daemon-to-daemon socket running on IP {self.ip_address} and port {self.daemon_port}")
        self.client_socket.bind((self.ip_address, self.client_port))
        print(f"Daemon-to-client socket running on IP {self.ip_address} and port {self.client_port}")
        listen_to_client_thread = threading.Thread(target=self.listen_to_client)
        listen_to_client_thread.start()
        handshake_receiver_thread = threading.Thread(target=self.handshake_receiver)
        handshake_receiver_thread.start()
        message_forwarder_thread = threading.Thread(target=self.message_forwarder)
        message_forwarder_thread.start()

    def listen_to_client(self):
        # This function continuously listens for messages from the client
        # Determines the action based on the type of the message
        while True:
            message, address = self.client_socket.recvfrom(4096)
            type = self.controlTypes[message[:1]]
            message = message[2:].decode()
            # If the control type is connect, then the client is trying to connect to the daemon
            if type == "connect":
                # If there is a client already connected, then send an error message
                if self.client_connected:
                    message = b'\x02\x00' + "The daemon already connected to a client".encode()
                    self.client_socket.sendto(message, address)
                # If there is no client connected, then send a connection established message
                message = b'\x00\x00'
                self.client_socket.sendto(message, address)
                self.client_address = address
                self.client_connected = True
                # If the connection is established, then ask for the username
                message = b'\x00\x01' + "Please enter a username: ".encode()
                self.client_socket.sendto(message, self.client_address)
                username, address = self.client_socket.recvfrom(4096)
                username = username[2:].decode()
                self.client_username = username
                # If there is no pending request, then ask the client if they want to wait for a connection or start one
                if not self.pending_request:
                    message = b'\x05\x01' + "Do you want to wait for connection or start one? [wait/start]: ".encode()
                    self.client_socket.sendto(message, self.client_address)
                    wait_or_start, address = self.client_socket.recvfrom(4096)
                    wait_or_start = wait_or_start[2:].decode()
                    # If the clients starts a connection, then ask for the other daemon's IP address and start the handshake
                    if wait_or_start == "start":
                        # ask for other daemon ip
                        message = b'\x05\x01' + "Enter the other daemon's IP address: ".encode()
                        self.client_socket.sendto(message, self.client_address)
                        # receive other daemon ip
                        other_daemon_ip, address = self.client_socket.recvfrom(4096)
                        other_daemon_ip = other_daemon_ip[2:].decode()
                        self.other_daemon_ip = other_daemon_ip
                        # Get the other daemon's IP address and start the handshake
                        handshake_sender_thread = threading.Thread(target=self.handshake_sender)
                        handshake_sender_thread.start()
                    # If the client wait for a connection there is nothing to do on the daemon side
            elif type == "chat":
                # If the client is connected and wants to send a message, it will be put to the message buffer
                # An other thread continuously checks the message buffer and sends the messages to the other daemon
                message = SIMP_Socket(
                    type='chat',
                    operation='message',
                    sequence='request',
                    user=self.client_username,
                    payload=message
                )
                self.message_buffer.append(message)
            elif type == "quit":
                # If the client wants to quit, then send a fin to the other daemon
                FIN = SIMP_Socket(
                    type='control',
                    operation='fin',
                    sequence='request',
                    user=self.client_username,
                    payload=''
                )
                self.send_packet_daemon(FIN.encode())
                # Indicate that the daemon is waiting for the ack
                self.fin_sent = True
            elif type == "yesno":
                # This is a control type that is used to ask the client if they want to accept the connection
                if self.pending_request:
                    if message == "y":
                        # This is used to indicate that the client accepted the connection
                        self.accepted = True
                        pass
                    else:
                        # This is used to indicate that the client declined the connection
                        self.accepted = False
                        pass
            elif type == "reask":
                # In the case of a declined connection the daemon will ask the client again if they want to wait or start
                # This is the same as the first time the client connects
                message = b'\x05\x01' + "Do you want to wait for connection or start one? [wait/start]: ".encode()
                self.client_socket.sendto(message, self.client_address)
                # receive wait or start
                wait_or_start, address = self.client_socket.recvfrom(4096)
                wait_or_start = wait_or_start[2:].decode()
                if wait_or_start == "start":
                    # ask for other daemon ip
                    message = b'\x05\x01' + "Enter the other daemon's IP address: ".encode()
                    self.client_socket.sendto(message, self.client_address)
                    # receive other daemon ip
                    other_daemon_ip, address = self.client_socket.recvfrom(4096)
                    other_daemon_ip = other_daemon_ip[2:].decode()
                    self.other_daemon_ip = other_daemon_ip
                    # start handshake
                    handshake_sender_thread = threading.Thread(target=self.handshake_sender)
                    handshake_sender_thread.start()
            else:
                # Ignore the control types that are not used by the client
                pass

    def listen_to_daemon(self):
        # This function continuously listens for messages from the other daemon
        # Determines the action based on the type of the message
        while True:
            data, address = self.daemon_socket.recvfrom(4096)
            rec = SIMP_Socket()
            rec.decode(data)
            print("---------------------------------")
            print("Packet received from other daemon")
            rec.printData()
            print("---------------------------------")
            # If the other daemon sends a message, then send it to the client
            # Send an ack to the other daemon, that indicates that the message was received
            if rec.operation == "message":
                message = b'\x01\x00' + rec.payload.encode()
                self.client_socket.sendto(message, self.client_address)
                ack = SIMP_Socket(
                    type='control',
                    operation='ack',
                    sequence='response',
                    user=self.client_username,
                    payload=''
                )
                self.daemon_socket.sendto(ack.encode(), (self.other_daemon_ip, self.daemon_port))
            elif rec.operation == "fin":
                # If the other daemon sends a fin send an ack to the other daemon and close the connection
                ACK = SIMP_Socket(
                    type='control',
                    operation='ack',
                    sequence='response',
                    user=self.client_username,
                    payload=''
                )
                ACK_binary = ACK.encode()
                self.daemon_socket.sendto(ACK_binary, (self.other_daemon_ip, self.daemon_port))
                message = b'\x03\x00' + rec.payload.encode()
                self.client_socket.sendto(message, self.client_address)
                # The connection to the client and the other daemon is closed, everything is reset
                self.client_connected = False
                self.client_address = None
                self.other_daemon_ip = None
                handshake_receiver_thread = threading.Thread(target=self.handshake_receiver)
                handshake_receiver_thread.start()
            elif rec.operation == "ack":
                # If the ack is received there can be two cases
                # Either it is an ack for the fin
                if self.fin_sent:
                    # In this case it is indicated that the connection can be closed
                    # Everything is reset
                    message = b'\x03\x00'
                    self.client_socket.sendto(message, self.client_address)
                    self.client_connected = False
                    self.client_address = None
                    self.other_daemon_ip = None
                    self.other_daemon_connected = False
                    self.fin_sent = False
                    handshake_receiver_thread = threading.Thread(target=self.handshake_receiver)
                    handshake_receiver_thread.start()
                    break
                # Or it is an ack for a message
                # In this case the message is removed from the message buffer
                if self.message_sent:
                    self.ack_received = True
                    self.message_sent = False
            elif rec.operation == "syn" and self.other_daemon_connected:
                # If the client is in a chat with another client, send the third person a message that the client is busy
                ERR = SIMP_Socket(
                    type='control',
                    operation='error',
                    sequence='response',
                    user=self.client_username,
                    payload="User is busy in another chat"
                )
                self.daemon_socket.sendto(ERR.encode(), address)

    def message_forwarder(self):
        while True:
            # If the message buffer is not empty, then send the first message to the other daemon
            if len(self.message_buffer) > 0:
                message = self.message_buffer.pop(0)
                self.daemon_socket.sendto(message.encode(), (self.other_daemon_ip, self.daemon_port))
                # This indicates that the message was sent, and the daemon is waiting for the ack
                self.message_sent = True
                print("---------------------------------")
                print("Message sent to other daemon")
                message.printData()
                # A timer is started
                timer = 0
                # It checks for 5 seconds if the ack was received
                while not self.ack_received and timer < 5:
                    time.sleep(0.01)
                    timer += 0.01
                # If the timer ran out, then the message is put back to the message buffer to be sent again
                if timer >= 5:
                    # put back message to buffer first place
                    self.message_buffer.insert(0, message)
                    print("Message not acknowledged, resending")
                    print("---------------------------------")
                    self.ack_received = False
                    continue
                print("Message acknowledged")
                print("---------------------------------")
                # reset ack received
                self.ack_received = False

    def send_packet_daemon(self, data):
        # This function is used to send a packet to the other daemon
        # We can only send a packet if every message before was acknowledged
        if not self.message_buffer:
            self.daemon_socket.sendto(data, (self.other_daemon_ip, self.daemon_port))

    def handshake_sender(self):
        # The handshake is started by sending a syn to the other daemon
        SYN = SIMP_Socket(
            type='control',
            operation='syn',
            sequence='request',
            user=self.client_username,
            payload=''
        )
        SYN_binary = SYN.encode()
        # SENDING SYN
        self.daemon_socket.sendto(SYN_binary, (self.other_daemon_ip, self.daemon_port))

    def handshake_receiver(self):
        print("Waiting for handshake")
        # WAITING FOR SYN
        while True:
            data, address = self.daemon_socket.recvfrom(4096)
            rec = SIMP_Socket()
            rec.decode(data)
            if rec.type == "control" and rec.operation == "syn":
                print("syn received")
                self.pending_request = True
                self.pending_request_data = (rec.user, address)
                # If a SYN is received but no client is connected wait for the client to connect
                # then ask the client if they want to accept the connection
                while not self.client_connected:
                    time.sleep(0.01)
                    pass
                if self.client_connected:
                    # Handling that the client is already connected to another daemon is done in at a different place
                    # ask client if they want to accept the connection
                    message = b'\x04\x01' + f"Request from user {self.pending_request_data[0]} address: {self.pending_request_data[1][0]}:{self.pending_request_data[1][1]}. Do you want to accept? [y/n]: ".encode()
                    self.client_socket.sendto(message, self.client_address)
                    self.other_daemon_ip = address[0]
                    # receive accept or decline
                    while self.accepted is None:
                        time.sleep(0.01)
                        pass
                    # When a client is connected ask them if they want to accept the connection
                    if self.accepted:
                        # If the client accepts the connection, then send a synack to the other daemon
                        self.accepted = None
                        pass
                    else:
                        # If the client declines the connection, then send a FIN to the other daemon
                        FIN = SIMP_Socket(
                            type='control',
                            operation='fin',
                            sequence='response',
                            user=self.client_username,
                            payload='Error: The other client declined your request'
                        )
                        FIN_binary = FIN.encode()
                        # Reset the waiting for handshake
                        print("Fin sent")
                        self.daemon_socket.sendto(FIN_binary, (self.other_daemon_ip, self.daemon_port))
                        handshake_receiver_thread = threading.Thread(target=self.handshake_receiver)
                        handshake_receiver_thread.start()
                        self.accepted = None
                        self.pending_request = False
                        break
                    # If they accept the connection, then send a synack to the other daemon
                    self.pending_request = False
                    # SENDING SYNACK
                    SYN = SIMP_Socket(
                        type='control',
                        operation='syn',
                        sequence='response',
                        user=self.client_username,
                        payload=''
                    )
                    ACK = SIMP_Socket(
                        type='control',
                        operation='ack',
                        sequence='response',
                        user=self.client_username,
                        payload=''
                    )
                    SYN_binary = SYN.encode()
                    ACK_binary = ACK.encode()
                    # Achieve SYNACK by ORing the binary of SYN and ACK
                    SYN_ACK_binary = bytearray(b1 | b2 for b1, b2 in zip(ACK_binary, SYN_binary))
                    self.daemon_socket.sendto(bytes(SYN_ACK_binary), (self.other_daemon_ip, self.daemon_port))
                    print("synack sent")
            if rec.type == "control" and rec.operation == "ack":
                # If the ack is received, then the connection is established
                self.other_daemon_connected = True
                print("ACK received")
                # send connection established to client
                message = b'\x06\x00' + "Connection established".encode()
                self.client_socket.sendto(message, self.client_address)
                listen_to_daemon_thread = threading.Thread(target=self.listen_to_daemon)
                listen_to_daemon_thread.start()
                break
            if rec.type == "control" and rec.operation == "fin":
                print("FIN received, connection was declined")
                # If a fin is received, the other client declined the connection
                # send error to client
                message = b'\x02\x00' + rec.payload.encode()
                self.client_socket.sendto(message, self.client_address)
                # Reset the waiting for handshake
                self.client_connected = False
                self.client_address = None
                self.other_daemon_ip = None
                handshake_receiver_thread = threading.Thread(target=self.handshake_receiver)
                handshake_receiver_thread.start()
                break
            if rec.type == "control" and rec.operation == "synack":
                # If a synack is received, then the connection is established
                # SENDING ACK
                ACK = SIMP_Socket(
                    type='control',
                    operation='ack',
                    sequence='request',
                    user=self.client_username,
                    payload=''
                )
                ACK_binary = ACK.encode()
                self.daemon_socket.sendto(ACK_binary, (self.other_daemon_ip, self.daemon_port))
                self.other_daemon_connected = True
                print("sending ack")
                # send connection established to client
                message = b'\x06\x00' + "Connection established".encode()
                self.client_socket.sendto(message, self.client_address)
                listen_to_daemon_thread = threading.Thread(target=self.listen_to_daemon)
                listen_to_daemon_thread.start()
                break
            if rec.type == "control" and rec.operation == "error":
                # If an error is received, then the other client is already connected to another daemon
                # send error to client
                message = b'\x02\x00' + rec.payload.encode()
                self.client_socket.sendto(message, self.client_address)
                # Reset everything
                self.client_connected = False
                self.client_address = None
                self.other_daemon_ip = None
                handshake_receiver_thread = threading.Thread(target=self.handshake_receiver)
                handshake_receiver_thread.start()
                break


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 simp_daemon.py <ip_address>")
        sys.exit(1)

    daemon_ip = sys.argv[1]
    daemon = SimpDaemon(daemon_ip)

import os
import socket
import sys
import threading


class SimpClient:
    def __init__(self, ip_address):
        # The daemon's IP address and port
        self.daemon_ip = ip_address
        self.daemon_port = 7778
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Control types, used to determine the type of message received from the daemon
        self.controlTypes = {
            b"\x00": "connect",
            b"\x01": "chat",
            b"\x02": "error",
            b"\x03": "quit",
            b"\x04": "connreq",
            b'\x06': 'connestab',
            b"\x05": "waitorstart"
        }
        self.start()

    '''
    Types in the daemon - client messaging protocol:
    --
    message : 1byte - type + 1byte - response (x01 if waiting for response, x00 if not) + payload
    --
    x00 - Connect
    x01 - Chat
    x02 - Error
    x03 - Close/Quit
    x04 - Connection request
    x05 - Wait or start
    x06 - Connection established
    x09 - Connection request answer
    --
    '''

    def split_data(self, data):
        # This function splits the data received from the daemon into the type of message, whether the client should
        # wait for a response and the message itself
        # The waiting for response is not used. I wanted to implement it, but at the end I decided to not use it.
        type = self.controlTypes[data[:1]]
        wait_for_response = (data[1:2] == b"x01")
        message = data[2:].decode()
        return type, wait_for_response, message

    def start(self):
        # Send a connect message to the daemon
        message = b'\x00\x01'
        self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))
        # If the daemon is running, it will send a response
        # Asking for username or an error, that the daemon has a client connected
        msg, address = self.client_socket.recvfrom(4096)
        type, wait_for_response, msg = self.split_data(msg)
        if type == "error":
            print(msg)
            sys.exit(1)
        # If it is not an error, it is asking for username
        print("Connected to daemon successfully!")
        # Ask for username
        msg, address = self.client_socket.recvfrom(4096)
        type, wait_for_response, msg = self.split_data(msg)
        username = b'\x00\x01' + input(msg).encode()
        # Send username to the daemon
        self.client_socket.sendto(username, (self.daemon_ip, self.daemon_port))
        # Start a thread that listens to the daemon
        listen_to_daemon_thread = threading.Thread(target=self.listen_to_daemon)
        listen_to_daemon_thread.start()

    def listen_to_daemon(self):
        while True:
            # This thread listens to the daemon and prints the messages received from it
            data, address = self.client_socket.recvfrom(4096)
            type = self.controlTypes[data[:1]]
            message = data[2:].decode()
            # Depending on the type of message, the client will decide what to do
            if type == "connreq":
                # The daemon informs the client, that another client wants to connect
                answer = input(message)
                message = b'\x09\x01' + answer.encode()
                self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))
                if answer == "y":
                    # If the answer is yes we don't need to do anything, the daemon will send the data
                    pass
                elif answer == "n":
                    # If the answer is no, we need to send a message to the daemon, that we don't want to connect
                    # ,and it should reask for action
                    message = b'\x07'
                    self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))
                    pass
            elif type == "waitorstart":
                # The daemon asks the client whether it wants to wait for a connection or start a connection
                answer = input(message)
                message = b'\x05\x00' + answer.encode()
                self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))
                # If the answer is start, the client needs to send the IP address of the other client
                if answer == "start":
                    msg, address = self.client_socket.recvfrom(4096)
                    type, wait_for_response, msg = self.split_data(msg)
                    other_daemon_ip = input(msg)
                    message = b'\x05\x00' + other_daemon_ip.encode()
                    self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))
                # If the answer is wait, the client will wait for the other client to connect indefinitely
                elif answer == "wait":
                    print("Waiting for connection...")
            elif type == "error":
                # If the client receives an error message, it will print it and terminate the connection to the daemon
                print(message)
                print("Closing connection")
                sys.exit(1)
            elif type == "connestab":
                # If the connection is established, the client will start a thread that will start sending chat messages
                print("Connection established!")
                print('Type your message below (send "q" to disconnect): ')
                send_chat_message_to_daemon_thread = threading.Thread(target=self.send_chat_message_to_daemon)
                send_chat_message_to_daemon_thread.start()
            elif type == "chat":
                # If the client receives a chat message, it will print it
                print("\nOther: " + message + "\nYou: ", end='')
            elif type == "quit":
                # If the client receives a quit message, it will print it and terminate the connection to the daemon
                print("\nYou or the other client terminated the connection.")
                # I have to do a hard exit, because the thread that sends chat messages is still running
                os._exit(0)

    def send_chat_message_to_daemon(self):
        # This function continuously asks the user for a message and sends it to the daemon
        message = input("You: ")
        while message != "q":
            message = b'\x01\x01' + message.encode()
            self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))
            message = input("You: ")
        # If the user sends "q", the client will send a quit message to the daemon to start the fin sequence
        print("Closing connection")
        message = b'\x03\x00'
        self.client_socket.sendto(message, (self.daemon_ip, self.daemon_port))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 simp_client.py <ip_address>")
        sys.exit(1)

    daemon_ip = sys.argv[1]
    daemon = SimpClient(daemon_ip)

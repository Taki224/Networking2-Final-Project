# Networking Technologies and Management Systems II
# Programming Project

### By: Balint Takacs and Gergely Lendvay

---

## Usage

The project requires no additional installations, as it relies on libraries that are part of the standard Python 3 library.

To run the project, follow these steps:
1. Start the first daemon using the command: `python3 simp_daemon.py <IP_ADDRESS>`
(for testing we used 127.0.0.1)
2. Start the second daemon using the command: `python3 simp_daemon.py <IP_ADDRESS>`
(for testing we used the private IP address of the computer)\
![Screenshot 2023-12-19 at 20.09.57.png](src%2FScreenshot%202023-12-19%20at%2020.09.57.png)
3. Connect to the daemon with a client. (If the daemon is running it will ask for username)\
![Screenshot 2023-12-19 at 20.11.30.png](src%2FScreenshot%202023-12-19%20at%2020.11.30.png)
4. After this, one of the following 2 will hapen:
   - There is already a request for chat. In this case the client will be asked if they want to connect or not.\
   ![Screenshot 2023-12-19 at 20.14.36.png](src%2FScreenshot%202023-12-19%20at%2020.14.36.png)
   - There is no request for chat. In this case the client will be asked if they want to wait for a request or start one.\
   ![Screenshot 2023-12-19 at 20.15.40.png](src%2FScreenshot%202023-12-19%20at%2020.15.40.png)
5. Wait or start
   - If the client choose wait, it will wait for a request indefinitely. (Currently there is no way to go back or disconnect in this stage. The error in case of receiving a request while in the choosing state is not handled, so the client must be in waiting state to receive connection request correctly.)\
   ![Screenshot 2023-12-19 at 20.24.24.png](src%2FScreenshot%202023-12-19%20at%2020.24.24.png)
   - If the client choose start, it will ask for the IP address of the other daemon. After the IP address is sent the daemon will send the request to the other daemon. After this the client will wait for the other daemon to accept or reject the request.\
   ![Screenshot 2023-12-19 at 20.24.40.png](src%2FScreenshot%202023-12-19%20at%2020.24.40.png)
6. Accept or decline
   - If the client choose accept, the connection will be established by a three-way handshake and the chat will start.\
   ![Screenshot 2023-12-19 at 20.30.47.png](src%2FScreenshot%202023-12-19%20at%2020.30.47.png)
   - If the client choose decline, the connection will be terminated and the client will be asked if they want to wait or start again. A FIN will be sent to the other client, and they get kicked out from the daemon with an error message.\
   ![Screenshot 2023-12-19 at 20.27.19.png](src%2FScreenshot%202023-12-19%20at%2020.27.19.png)
7. Message sending:\
   Both clients can send messages to each other. The messages will be displayed on the screen.
   When a message sent the client is waiting for an ack. Other messages are stores in a buffer before sending. If the ack from the other client does not arrive in 5 seconds the message will be sent again.\
   (The stop and wait only works for the message, for other control packets it is not.)\
   ![Screenshot 2023-12-19 at 20.33.24.png](src%2FScreenshot%202023-12-19%20at%2020.33.24.png)
9. Terminating the connection:\
Both clients can terminate the connection during the chat with sending "q" as message. In this case a FIN will be sent to the other client. When the client receives a FIN it will send an ACK and terminate the connection. When the terminating client gets the ACK it will terminate the connection on its wn end as well.\
![Screenshot 2023-12-19 at 20.39.49.png](src%2FScreenshot%202023-12-19%20at%2020.39.49.png)

## Communication protocol between the client and the daemon

All the messages between the client and the daemon are starting with a byte that indicates the type of the message. Action is taken based on this byte.

## SIMP protocol
An instance of a SIMP protocol server as the packet that will be sent over the network.\
In the code the packet is created by setting the fields of the class with readable values.\
The `encode()` function will translate the packet to a byte array that can be sent over the network.
```
message = SIMP_Socket(
type='chat',
operation='message',
sequence='request',
user='test',
payload='Hello World'
)
```
will be encoded to:
`b'\x02\x01\x00test\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0bHello World'`

There are fix lengths for every field in the packet. The username field contains the username in readable format and the rest is padded up to 32 bytes, that is the max length of the username.

This byte array will be decoded on the other side and translated back to a SIMP_Socket object.



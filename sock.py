import struct

class SIMP_Socket:
    def __init__(self, type=None, operation=None, sequence=None, user=None, length=None, payload=None):
        self.type = type
        self.operation = operation
        self.sequence = sequence
        self.user = user
        self.length = length
        self.payload = payload

    def encode(self):
        # Convert type to binary
        if self.type == 'control':
            type_binary = struct.pack('B', 0x01)
        elif self.type == 'chat':
            type_binary = struct.pack('B', 0x02)
        else:
            raise Exception('Invalid type')

        # Convert operation to binary
        if self.type == 'control':
            if self.operation == 'error':
                operation_binary = struct.pack('B', 0x01)
            elif self.operation == 'syn':
                operation_binary = struct.pack('B', 0x02)
            elif self.operation == 'ack':
                operation_binary = struct.pack('B', 0x04)
            elif self.operation == 'fin':
                operation_binary = struct.pack('B', 0x08)
            else:
                raise Exception('Invalid operation')
        elif self.type == 'chat':
            operation_binary = struct.pack('B', 0x01)
        else:
            raise Exception('Invalid operation')

        # Convert sequence to binary
        if self.sequence == 'request':
            sequence_binary = struct.pack('B', 0x00)
        elif self.sequence == 'response':
            sequence_binary = struct.pack('B', 0x01)
        else:
            raise Exception('Invalid sequence')

        # Convert username to 32 bytes, padded with null bytes, only pad up to 32 bytes
        user_binary = self.user.encode('ascii')
        user_binary = user_binary.ljust(32, b'\x00')

        # Convert payload to binary
        payload_binary = self.payload.encode('ascii')

        # Calculate length of payload
        self.length = len(payload_binary)

        # Convert length to bytes
        length_bytes = self.length.to_bytes(4, 'big')  # 'big' or 'little' depending on your needs

        return type_binary + operation_binary + sequence_binary + user_binary + length_bytes + payload_binary

    def decode(self, bytestream):
        # Convert type to string
        if bytestream[0] == 0x01:
            self.type = 'control'
        elif bytestream[0] == 0x02:
            self.type = 'chat'
        else:
            raise Exception('Invalid type')

        # Convert operation to string
        if self.type == 'control':
            if bytestream[1] == 0x01:
                self.operation = 'error'
            elif bytestream[1] == 0x02:
                self.operation = 'syn'
            elif bytestream[1] == 0x04:
                self.operation = 'ack'
            elif bytestream[1] == 0x08:
                self.operation = 'fin'
            elif bytestream[1] == 0x06:
                # The "0x06" is the result of a bitwise or between 0x02 and 0x04
                self.operation = 'synack'
            else:
                self.operation = 'unknown'
        elif self.type == 'chat':
            self.operation = 'message'
        else:
            raise Exception('Invalid operation')

        # Convert sequence to string
        if bytestream[2] == 0x00:
            self.sequence = 'request'
        elif bytestream[2] == 0x01:
            self.sequence = 'response'
        else:
            raise Exception('Invalid sequence')

        # Convert username to string, remove null bytes
        self.user = bytestream[3:35].decode('ascii').strip('\x00')

        # Convert length to int
        self.length = int.from_bytes(bytestream[35:39], 'big')

        # Convert payload to string
        self.payload = bytestream[39:].decode('ascii')

    def printData(self):
        print('Type: {}'.format(self.type))
        print('Operation: {}'.format(self.operation))
        print('Sequence: {}'.format(self.sequence))
        print('User: {}'.format(self.user))
        print('Length: {}'.format(self.length))
        print('Payload: {}'.format(self.payload))

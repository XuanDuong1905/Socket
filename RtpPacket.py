import sys
from time import time

HEADER_SIZE = 12    # Kích thước cố định của RTP Header (12 bytes)


class RtpPacket:    
    def __init__(self):
        self.header = bytearray(HEADER_SIZE)
        self.payload = b''
    
    def encode(self, version, padding, extension, contributing_source_count, sequence_number, marker, payload_type, ssrc, payload, timestamp):
        header = bytearray(HEADER_SIZE)
        
        # Byte 0: Version, Padding, Extension, CC
        header[0] = ((version << 6) | (padding << 5) | (extension << 4) | contributing_source_count)
        
        # Byte 1: Marker, Payload Type
        header[1] = (marker << 7) | payload_type
        
        # Byte 2-3: Sequence Number (16 bits)
        header[2] = (sequence_number >> 8) & 0xFF
        header[3] = sequence_number & 0xFF
        
        # Byte 4-7: Timestamp (32 bits)
        header[4] = (timestamp >> 24) & 0xFF
        header[5] = (timestamp >> 16) & 0xFF
        header[6] = (timestamp >> 8) & 0xFF
        header[7] = timestamp & 0xFF
        
        # Byte 8-11: SSRC (32 bits)
        header[8] = (ssrc >> 24) & 0xFF
        header[9] = (ssrc >> 16) & 0xFF
        header[10] = (ssrc >> 8) & 0xFF
        header[11] = ssrc & 0xFF
        
        self.header = header
        self.payload = payload
    
    def decode(self, byte_stream):
        self.header = bytearray(byte_stream[:HEADER_SIZE]) #12 bytes đầu tới header
        self.payload = byte_stream[HEADER_SIZE:] #header tới payload
    
    def version(self):
        return int(self.header[0] >> 6) #lấy version từ 2 bits đầu tiên
    
    def seqNum(self):
        sequence_number = self.header[2] << 8 | self.header[3] #lấy sequence number từ 2 bytes thứ 2 và 3(16 bits)
        return int(sequence_number)
    
    def timestamp(self):
        timestamp = (self.header[4] << 24 | self.header[5] << 16 | self.header[6] << 8 | self.header[7]) #lấy timestamp từ 4 bytes thứ 4 đến 7(32 bits)
        return int(timestamp)
    
    def payloadType(self):
        payload_type = self.header[1] & 127
        return int(payload_type)
    
    def getPayload(self):
        return self.payload #lấy payload từ gói tin
    
    def getPacket(self):
        return self.header + self.payload #tổng hợp gói tin để gửi đi
    
    def getMarker(self):
        marker = (self.header[1] >> 7) & 1 #lấy marker từ bit đầu tiên của byte 1
        return marker
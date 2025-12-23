import sys
from time import time

HEADER_SIZE = 12    # Kích thước cố định của RTP Header (12 bytes)


class RtpPacket:
    """
    Lớp đại diện cho một gói tin RTP (Real-time Transport Protocol)
    """
    
    def __init__(self):
        self.header = bytearray(HEADER_SIZE)
        self.payload = b''
    
    def encode(self, version, padding, extension, contributing_source_count, 
               sequence_number, marker, payload_type, ssrc, payload, timestamp):
        """
        Đóng gói dữ liệu vào header RTP
        
        Cấu trúc RTP Header (12 bytes):
        - Byte 0: V(2) | P(1) | X(1) | CC(4)
        - Byte 1: M(1) | PT(7)
        - Byte 2-3: Sequence Number (16 bits)
        - Byte 4-7: Timestamp (32 bits)
        - Byte 8-11: SSRC (32 bits)
        
        Args:
            version: Phiên bản RTP (thường là 2)
            padding: Có padding hay không (0 hoặc 1)
            extension: Có extension header hay không (0 hoặc 1)
            contributing_source_count: Số lượng CSRC (0-15)
            sequence_number: Số thứ tự gói tin (0-65535)
            marker: Bit đánh dấu (thường dùng cho gói cuối frame)
            payload_type: Loại payload (26 cho MJPEG)
            ssrc: Synchronization Source identifier
            payload: Dữ liệu thực tế (video/audio)
            timestamp: Thời gian của gói tin
        """
        header = bytearray(HEADER_SIZE)
        
        # Byte 0: Version, Padding, Extension, CC
        header[0] = ((version << 6) | 
                    (padding << 5) | 
                    (extension << 4) | 
                    contributing_source_count)
        
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
        """
        Giải mã gói tin RTP từ chuỗi byte nhận được
        
        Args:
            byte_stream: Dữ liệu thô nhận từ socket
        """
        self.header = bytearray(byte_stream[:HEADER_SIZE])
        self.payload = byte_stream[HEADER_SIZE:]
    
    def version(self):
        """
        Lấy phiên bản RTP (2 bits đầu tiên)
        
        Returns:
            int: Phiên bản RTP (thường là 2)
        """
        return int(self.header[0] >> 6)
    
    def seqNum(self):
        """
        Lấy Sequence Number (16 bits)
        
        Returns:
            int: Số thứ tự gói tin (0-65535)
        """
        sequence_number = self.header[2] << 8 | self.header[3]
        return int(sequence_number)
    
    def timestamp(self):
        """
        Lấy Timestamp (32 bits)
        
        Returns:
            int: Timestamp của gói tin
        """
        timestamp = (self.header[4] << 24 | 
                    self.header[5] << 16 | 
                    self.header[6] << 8 | 
                    self.header[7])
        return int(timestamp)
    
    def payloadType(self):
        """
        Lấy Payload Type (7 bits cuối của byte 1)
        
        Returns:
            int: Loại payload (26 = MJPEG)
        """
        payload_type = self.header[1] & 127
        return int(payload_type)
    
    def getPayload(self):
        """
        Lấy phần dữ liệu payload (video/audio data)
        
        Returns:
            bytes: Dữ liệu thực tế của gói tin
        """
        return self.payload
    
    def getPacket(self):
        """
        Lấy toàn bộ gói tin (header + payload) để gửi đi
        
        Returns:
            bytes: Header + Payload
        """
        return self.header + self.payload
    
    def getMarker(self):
        """
        Lấy bit Marker (bit đầu tiên của byte 1)
        Bit này thường đánh dấu gói cuối cùng của một frame
        
        Returns:
            int: 0 hoặc 1
        """
        marker = (self.header[1] >> 7) & 1
        return marker
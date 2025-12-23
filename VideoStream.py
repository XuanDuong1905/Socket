class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError(f"Cannot open file: {filename}")
        
        self.frame_number = 0
    
    def nextFrame(self):
        start_position = self.file.tell()
        data = self.file.read(5)  # Đọc 5 bytes đầu (độ dài frame)
        
        if not data:
            return None 
        
        try:
            frame_length = int(data)
            frame_data = self.file.read(frame_length)
            self.frame_number += 1
            return frame_data
        
        except ValueError:
            # Fallback: Quét tìm marker kết thúc JPEG (FF D9)
            self.file.seek(start_position)
            full_data = bytearray()
            
            while True:
                chunk = self.file.read(1024)
                if not chunk:
                    break
                
                full_data.extend(chunk)
                
                # Tìm End Of Image (EOI) marker
                end_position = full_data.find(b'\xff\xd9')
                
                if end_position != -1:
                    frame_data = bytes(full_data[:end_position + 2])
                    
                    # Dời con trỏ file đến frame tiếp theo
                    self.file.seek(start_position + len(frame_data))
                    self.frame_number += 1
                    return frame_data
            
            return None
    
    def frameNbr(self):
        return self.frame_number
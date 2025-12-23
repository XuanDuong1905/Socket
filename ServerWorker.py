from random import randint
import sys
import traceback
import threading
import socket
import time

from VideoStream import VideoStream
from RtpPacket import RtpPacket


class ServerWorker:
    """
    Worker xử lý một client RTSP và gửi luồng RTP
    """
    
    # Các loại RTSP request
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    
    # Các trạng thái của server worker
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT
    
    # Các mã phản hồi RTSP
    OK_200 = 0 #nhận được request thành công
    FILE_NOT_FOUND_404 = 1 #file không tìm thấy
    CONNECTION_ERROR_500 = 2 #lỗi kết nối
    
    def __init__(self, client_info):
        self.client_info = client_info
        self.client_info['sequence_number'] = 0
    
    def run(self):
        #tạo một threads để nhận và xử lý request từ client song song với thread chính đảm bảo phục vụ được nhiều client cùng lúc
        threading.Thread(target=self.receive_rtsp_request).start()
    
    def receive_rtsp_request(self):
        connection = self.client_info['rtsp_socket'][0] #lấy ra client socket
        
        while True:
            try:
                data = connection.recv(256)
                
                if data:
                    print("Data received:\n" + data.decode("utf-8"))
                    self.process_rtsp_request(data.decode("utf-8"))
                else:
                    print("Client closed connection")
                    break
                    
            except ConnectionResetError:
                print("Client reset connection")
                break
            except BrokenPipeError:
                print("Broken pipe")
                break
            except OSError as e:
                # Kiểm tra lỗi socket cụ thể trên Windows
                if e.winerror == 10038:
                    print("Socket closed (TEARDOWN)")
                    break
                else:
                    print(f"OSError: {e}")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Socket error: {type(e).__name__}: {e}")
                break
    
    def process_rtsp_request(self, data):
        """
        Example:
        SETUP movie.Mjpeg RTSP/1.0
        CSeq: 1
        Transport: RTP/UDP; client_port=5004
        """
        request_lines = data.split('\n')
        request_line = request_lines[0].split(' ')
        
        request_type = request_line[0] #có thể là setup, play, pause, teardown
        filename = request_line[1] #tên file video
        sequence_line = request_lines[1].split(' ') #lấy ra sequence number
        
        # Xử lý SETUP
        if request_type == self.SETUP:
            if self.state == self.INIT:
                print("Processing SETUP\n")
                
                try:
                    self.client_info['video_stream'] = VideoStream(filename)
                    self.state = self.READY
                except IOError:
                    self.reply_rtsp(self.FILE_NOT_FOUND_404, sequence_line[1])
                    return
                
                # Tạo Session ID ngẫu nhiên
                self.client_info['session'] = randint(100000, 999999)
                self.reply_rtsp(self.OK_200, sequence_line[1])
                
                # Lấy RTP port từ client
                self.client_info['rtp_port'] = request_lines[2].split(' ')[3]
        
        # Xử lý PLAY
        elif request_type == self.PLAY:
            if self.state == self.READY:
                print("Processing PLAY\n")
                self.state = self.PLAYING
                
                # Tạo socket UDP để gửi RTP
                self.client_info["rtp_socket"] = socket.socket(
                    socket.AF_INET, 
                    socket.SOCK_DGRAM
                )
                
                self.reply_rtsp(self.OK_200, sequence_line[1])
                
                # Tạo event và thread để gửi RTP
                self.client_info['event'] = threading.Event()
                self.client_info['worker'] = threading.Thread(target=self.send_rtp)
                self.client_info['worker'].start()
        
        # Xử lý PAUSE
        elif request_type == self.PAUSE:
            if self.state == self.PLAYING:
                print("Processing PAUSE\n")
                self.state = self.READY
                self.client_info['event'].set()
                self.reply_rtsp(self.OK_200, sequence_line[1])
        
        # Xử lý TEARDOWN
        elif request_type == self.TEARDOWN:
            print("Processing TEARDOWN\n")
            
            if 'event' in self.client_info:
                self.client_info['event'].set()
            
            self.reply_rtsp(self.OK_200, sequence_line[1])
            
            try:
                if 'rtp_socket' in self.client_info:
                    self.client_info['rtp_socket'].close()
            except:
                pass
            
            try:
                connection = self.client_info['rtsp_socket'][0]
                connection.close()
                print("TCP socket closed")
            except Exception as e:
                print(f"Error closing socket: {e}")
                pass
            
            return
    
    def send_rtp(self):
        max_payload_size = 1400  # Kích thước payload tối đa
        
        while True:
            # Chờ ~30ms (tương đương 30fps)
            self.client_info['event'].wait(0.033)
            
            # Kiểm tra tín hiệu dừng
            if self.client_info['event'].isSet():
                break
            
            # Lấy frame tiếp theo
            frame_data = self.client_info['video_stream'].nextFrame()
            
            if frame_data:
                frame_number = self.client_info['video_stream'].frameNbr()
                
                try:
                    client_address = self.client_info['rtsp_socket'][1][0]
                    client_port = int(self.client_info['rtp_port'])
                    
                    data_length = len(frame_data)
                    current_index = 0
                    packet_count = 0
                    
                    while current_index < data_length:
                        if self.client_info['event'].isSet():
                            break
                        
                        #Fragment cho Advanced
                        chunk = frame_data[current_index:current_index + max_payload_size]
                        current_index += max_payload_size
                        
                        if current_index >= data_length:
                            marker = 1  
                        else:
                            marker = 0  
                        
                        self.client_info['sequence_number'] += 1
                        
                        packet = self.make_rtp_packet(
                            chunk, 
                            self.client_info['sequence_number'],
                            marker,
                            frame_number
                        )
                        
                        if self.state == self.PLAYING:
                            try:
                                self.client_info['rtp_socket'].sendto(
                                    packet,
                                    (client_address, client_port)
                                )
                                
                                packet_count += 1
                                if packet_count % 20 == 0:
                                    time.sleep(0.002)
                                    
                            except OSError as e:
                                if e.winerror == 10038:
                                    print("Connection closed")
                                else:
                                    print(f"Error sending RTP: {e}")
                                    
                except:
                    print("Connection Error")
                    traceback.print_exc(file=sys.stdout)
    
    def make_rtp_packet(self, payload, sequence_number, marker, frame_number):
        version = 2
        padding = 0
        extension = 0
        contributing_source_count = 0
        payload_type = 26  # MJPEG
        ssrc = 0
        
        clock_rate = 90000  # Tần số đồng hồ chuẩn cho video
        frames_per_second = 30
        timestamp_step = clock_rate // frames_per_second
        
        if not hasattr(self, "_timestamp_base"):
            self._timestamp_base = randint(0, 0xFFFFFFFF) #giá trị lớn nhất của 32 bit
        
        timestamp = (self._timestamp_base + 
                    frame_number * timestamp_step) & 0xFFFFFFFF #mod về đúng 32 bit chuẩn quy tắc
        
        packet = RtpPacket()
        packet.encode(
            version,
            padding,
            extension,
            contributing_source_count,
            sequence_number,
            marker,
            payload_type,
            ssrc,
            payload,
            timestamp
        )
        
        return packet.getPacket()
    
    def reply_rtsp(self, response_code, sequence_number):
        try:
            connection = self.client_info['rtsp_socket'][0]
            
            #output ra màn hình máy server
            if response_code == self.OK_200:
                print("200 OK")
                reply = (f'RTSP/1.0 200 OK\n'
                        f'CSeq: {sequence_number}\n'
                        f'Session: {self.client_info["session"]}')
                connection.send(reply.encode())
            
            elif response_code == self.FILE_NOT_FOUND_404:
                print("404 NOT FOUND")
                reply = (f'RTSP/1.0 404 NOT FOUND\n'
                        f'CSeq: {sequence_number}\n'
                        f'Session: {self.client_info["session"]}')
                connection.send(reply.encode())
            
            elif response_code == self.CONNECTION_ERROR_500:
                print("500 CONNECTION ERROR")
                reply = (f'RTSP/1.0 500 CONNECTION ERROR\n'
                        f'CSeq: {sequence_number}\n'
                        f'Session: {self.client_info["session"]}')
                connection.send(reply.encode())
                
        except:
            print("Connection Error")
            traceback.print_exc(file=sys.stdout)
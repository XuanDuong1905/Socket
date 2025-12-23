from tkinter import *
from tkinter import messagebox as tk_message_box
from PIL import Image, ImageTk
import socket
import threading
import sys
import traceback
import os
import queue
import time
import io
from RtpPacket import RtpPacket


class Client:
    # Các trạng thái của client
    INIT = 0        # Khởi tạo - chưa có phiên làm việc
    READY = 1       # Sẵn sàng - đã setup xong
    PLAYING = 2     # Đang phát - đang nhận video
    state = INIT
    
    # Các loại request RTSP
    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    
    def __init__(self, master, server_address, server_port, rtp_port, filename):
        """
        Khởi tạo RTSP Client
        
        Args:
            master: Cửa sổ gốc Tkinter
            server_address: Địa chỉ IP của server
            server_port: Cổng RTSP của server
            rtp_port: Cổng RTP để nhận video
            filename: Tên file video yêu cầu
        """
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.create_widgets()
        
        # Thông tin kết nối
        self.server_address = server_address
        self.server_port = int(server_port)
        self.rtp_port = int(rtp_port)
        self.filename = filename
        
        # RTSP session info
        self.rtsp_sequence_number = 0
        self.session_id = 0
        self.request_sent = -1
        self.teardown_acknowledged = 0
        
        # Kết nối đến server
        self.connect_to_server()
        
        # Thống kê video
        self.frame_number = 0
        self.total_bytes_received = 0
        self.play_start_time = 0
        
        # Buffer và queue
        self.buffer_size = 20
        self.frame_buffer = queue.Queue(maxsize=1000)
        
        # Trạng thái nhận RTP
        self.is_first_packet = True
        self.expected_sequence_number = 0
        self.frame_data = b''
        self.is_corrupted = False
        
        # Hình ảnh đang chờ hiển thị
        self.pending_image = None
        self.pending_pil_image = None
        
        # Điều khiển thread
        self.is_first_play = True
        self.play_event = threading.Event()
        self.play_event.set()
        
        self.rtp_thread = None
        self.display_thread = None
        
        # Bắt đầu vòng lặp GUI
        self.start_gui_loop()
        
    def reset_receive_state(self):
        """Reset trạng thái nhận dữ liệu khi bắt đầu phát lại"""
        self.is_first_packet = True
        self.expected_sequence_number = 0
        self.frame_data = b''
        self.is_corrupted = False
    
    def start_gui_loop(self):
        """Vòng lặp cập nhật giao diện định kỳ"""
        if hasattr(self, 'pending_pil_image') and self.pending_pil_image:
            try:
                self.pending_image = ImageTk.PhotoImage(self.pending_pil_image)
                self.label.configure(image=self.pending_image, height=0)
                self.label.image = self.pending_image
                self.pending_pil_image = None
            except:
                pass
        self.master.after(20, self.start_gui_loop)
    
    def create_widgets(self):
        """Tạo các widget cho giao diện"""
        # Label hiển thị video
        self.label = Label(self.master, text="", font=("Helvetica", 14))
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)
        
        # Label hiển thị thời gian
        self.time_label = Label(self.master, text="00:00", font=("Helvetica", 12))
        self.time_label.grid(row=1, column=0, columnspan=4, pady=2)
        
        # Nút SETUP
        self.setup_button = Button(self.master, width=20, padx=3, pady=3)
        self.setup_button["text"] = "Setup"
        self.setup_button["command"] = self.setup_movie
        self.setup_button.grid(row=3, column=0, padx=2, pady=2)
        
        # Nút PLAY
        self.play_button = Button(self.master, width=20, padx=3, pady=3)
        self.play_button["text"] = "Play"
        self.play_button["command"] = self.play_movie
        self.play_button["state"] = "disabled"
        self.play_button.grid(row=3, column=1, padx=2, pady=2)
        
        # Nút PAUSE
        self.pause_button = Button(self.master, width=20, padx=3, pady=3)
        self.pause_button["text"] = "Pause"
        self.pause_button["command"] = self.pause_movie
        self.pause_button["state"] = "disabled"
        self.pause_button.grid(row=3, column=2, padx=2, pady=2)
        
        # Nút TEARDOWN
        self.teardown_button = Button(self.master, width=20, padx=3, pady=3)
        self.teardown_button["text"] = "Teardown"
        self.teardown_button["command"] = self.exit_client
        self.teardown_button["state"] = "disabled"
        self.teardown_button.grid(row=3, column=3, padx=2, pady=2)
    
    def setup_movie(self):
        """Xử lý nút Setup"""
        if self.state == self.INIT:
            self.send_rtsp_request(self.SETUP)
        self.setup_button["state"] = "disabled"
        self.teardown_button["state"] = "normal"
    
    def exit_client(self):
        """Xử lý nút Teardown - thoát ứng dụng"""
        self.send_rtsp_request(self.TEARDOWN)
        self.master.destroy()
    
    def pause_movie(self):
        """Xử lý nút Pause"""
        if self.state == self.PLAYING:
            self.play_event.set()
            
            # Đợi các thread dừng
            if self.rtp_thread and self.rtp_thread.is_alive():
                self.rtp_thread.join(timeout=0.8)
            if self.display_thread and self.display_thread.is_alive():
                self.display_thread.join(timeout=0.8)
            
            self.send_rtsp_request(self.PAUSE)
        
        self.pause_button["state"] = "disabled"
        self.play_button["state"] = "normal"
    
    def play_movie(self):
        """Xử lý nút Play"""
        self.play_event.clear()
        
        # Tạo thread nhận RTP nếu chưa có
        if (self.rtp_thread is None) or (not self.rtp_thread.is_alive()):
            self.rtp_thread = threading.Thread(target=self.listen_rtp, daemon=True)
            self.rtp_thread.start()
        
        # Tạo thread hiển thị nếu chưa có
        if (self.display_thread is None) or (not self.display_thread.is_alive()):
            self.display_thread = threading.Thread(target=self.display_loop, daemon=True)
            self.display_thread.start()
        
        self.send_rtsp_request(self.PLAY)
        
        self.play_button["state"] = "disabled"
        self.pause_button["state"] = "normal"
        
        # Xóa ảnh cũ khi bắt đầu phát lại
        if hasattr(self, 'pending_pil_image') and self.pending_pil_image is None:
            self.label.configure(text="")
    
    def listen_rtp(self):
        """Thread lắng nghe và nhận gói tin RTP"""
        jitter_buffer = {}
        max_buffer_size = 50
        
        while not self.play_event.is_set():
            if self.play_event.is_set():
                break
            try:
                data = self.rtp_socket.recv(40960)
                if data:
                    self.total_bytes_received += len(data)
                    
                    # Giải mã gói RTP
                    packet = RtpPacket()
                    packet.decode(data)
                    
                    sequence_number = packet.seqNum()
                    
                    # Lưu sequence number đầu tiên
                    if self.is_first_packet:
                        self.expected_sequence_number = sequence_number
                        self.is_first_packet = False
                    
                    # Thêm vào jitter buffer
                    jitter_buffer[sequence_number] = packet
                    
                    # Xử lý các gói trong buffer
                    while len(jitter_buffer) > 0:
                        if self.expected_sequence_number in jitter_buffer:
                            packet = jitter_buffer.pop(self.expected_sequence_number)
                            self.process_rtp_packet(packet)
                            
                            self.expected_sequence_number += 1
                            if self.expected_sequence_number > 65535:
                                self.expected_sequence_number = 0
                        
                        elif len(jitter_buffer) > max_buffer_size:
                            # Buffer đầy, có thể mất gói
                            keys = sorted(jitter_buffer.keys())
                            next_sequence = keys[0]
                            
                            lost_packets = next_sequence - self.expected_sequence_number
                            if lost_packets < 0:
                                lost_packets += 65536
                            
                            print(f"Lost {lost_packets} packets (Expected: {self.expected_sequence_number}, Got: {next_sequence})")
                            
                            self.is_corrupted = True
                            self.frame_data = b''
                            self.expected_sequence_number = next_sequence
                        else:
                            break
                        
            except socket.timeout:
                continue
            except Exception:
                if self.play_event.is_set() or self.teardown_acknowledged == 1:
                    break
                traceback.print_exc()
                continue
    
    def process_rtp_packet(self, packet):
        """
        Xử lý một gói tin RTP đã được sắp xếp
        
        Args:
            packet: Gói RTP đã giải mã
        """
        sequence_number = packet.seqNum()
        marker = packet.getMarker()
        
        print(f"Current Seq Num: {sequence_number}")
        
        # Ghép dữ liệu nếu frame không bị lỗi
        if not self.is_corrupted:
            self.frame_data += packet.getPayload()
        
        # Nếu là gói cuối cùng của frame
        if marker == 1:
            timestamp = packet.timestamp()
            payload = self.frame_data
            
            if not self.is_corrupted:
                # Kiểm tra header JPEG
                if payload.startswith(b'\xff\xd8'):
                    image_data = self.write_frame(payload, sequence_number, timestamp)
                    try:
                        self.frame_buffer.put(image_data, timeout=0.5)
                    except queue.Full:
                        pass
            
            # Reset cho frame tiếp theo
            self.frame_data = b''
            self.is_corrupted = False
    
    def monitor_buffering(self):
        """Theo dõi quá trình buffering"""
        if self.is_first_play:
            buffer_current_size = self.frame_buffer.qsize()
            
            if buffer_current_size < self.buffer_size:
                self.label.configure(text="Preparing for loading video...")
                self.master.after(100, self.monitor_buffering)
            else:
                self.send_rtsp_request(self.PAUSE)
                self.label.configure(text="Ready")
                self.play_button["state"] = "normal"
                self.is_first_play = False
    
    def display_loop(self):
        """Thread hiển thị video"""
        frames_per_second = 30
        frame_interval = 1.0 / frames_per_second
        startup_buffer = 1
        
        # Chờ buffer có ít nhất 1 frame
        start_time = time.time()
        while not self.play_event.is_set():
            if self.frame_buffer.qsize() >= startup_buffer:
                break
            if time.time() - start_time > 10.0:
                break
            time.sleep(0.005)
        
        last_time = time.time()
        
        # Vòng lặp hiển thị chính
        while not self.play_event.is_set():
            try:
                data = self.frame_buffer.get(timeout=0.05)
                image_data, timestamp = data
            except queue.Empty:
                continue
            
            now = time.time()
            self.update_movie(image_data, timestamp)
            
            elapsed_time = now - last_time
            queue_size = self.frame_buffer.qsize()
            
            # Điều chỉnh tốc độ dựa trên buffer
            if queue_size > 100:
                actual_interval = frame_interval * 0.95
            elif queue_size < 5:
                actual_interval = frame_interval * 1.05
            else:
                actual_interval = frame_interval
            
            sleep_time = actual_interval - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            last_time = time.time()
    
    def write_frame(self, data, sequence_number, timestamp):
        """
        Đóng gói dữ liệu frame
        
        Args:
            data: Dữ liệu JPEG
            sequence_number: Số thứ tự gói
            timestamp: Thời gian
            
        Returns:
            Tuple (data, timestamp)
        """
        return (data, timestamp)
    
    def update_movie(self, image_file, timestamp):
        """
        Cập nhật hình ảnh lên giao diện
        
        Args:
            image_file: Dữ liệu ảnh JPEG
            timestamp: Timestamp của frame
        """
        # Tính thời gian hiện tại
        if not hasattr(self, 'first_timestamp'):
            self.first_timestamp = timestamp
        
        current_time = (timestamp - self.first_timestamp) / 90000.0
        seconds = int(current_time)
        minutes = seconds // 60
        secs = seconds % 60
        self.time_label.configure(text=f"{minutes:02d}:{secs:02d}")
        
        try:
            stream = io.BytesIO(image_file)
            image = Image.open(stream)
            
            # Resize ảnh
            height = 500
            width, h = image.size
            width = int((height / h) * width)
            image.thumbnail((width, height), Image.Resampling.BILINEAR)
            
            self.pending_pil_image = image.copy()
        except Exception as e:
            print(f"Error processing frame: {e}")
    
    def connect_to_server(self):
        """Kết nối TCP đến RTSP Server"""
        self.rtsp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtsp_socket.connect((self.server_address, self.server_port))
        except:
            tk_message_box.showwarning('Connection Failed', 
                                      f'Connection to \'{self.server_address}\' failed.')
    
    def send_rtsp_request(self, request_code):
        """
        Gửi yêu cầu RTSP đến server
        
        Args:
            request_code: Mã loại request (SETUP/PLAY/PAUSE/TEARDOWN)
        """
        # SETUP
        if request_code == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.receive_rtsp_reply).start()
            self.rtsp_sequence_number += 1
            request = (f"SETUP {self.filename} RTSP/1.0\n"
                      f"CSeq: {self.rtsp_sequence_number}\n"
                      f"Transport: RTP/UDP; client_port= {self.rtp_port}")
            self.request_sent = self.SETUP
        
        # PLAY
        elif request_code == self.PLAY and self.state == self.READY:
            self.rtsp_sequence_number += 1
            request = (f"PLAY {self.filename} RTSP/1.0\n"
                      f"CSeq: {self.rtsp_sequence_number}\n"
                      f"Session: {self.session_id}")
            self.request_sent = self.PLAY
            self.play_start_time = time.time()
            self.total_bytes_received = 0
        
        # PAUSE
        elif request_code == self.PAUSE and self.state == self.PLAYING:
            self.rtsp_sequence_number += 1
            request = (f"PAUSE {self.filename} RTSP/1.0\n"
                      f"CSeq: {self.rtsp_sequence_number}\n"
                      f"Session: {self.session_id}")
            self.request_sent = self.PAUSE
        
        # TEARDOWN
        elif request_code == self.TEARDOWN and not self.state == self.INIT:
            self.rtsp_sequence_number += 1
            request = (f"TEARDOWN {self.filename} RTSP/1.0\n"
                      f"CSeq: {self.rtsp_sequence_number}\n"
                      f"Session: {self.session_id}")
            self.request_sent = self.TEARDOWN
        else:
            return
        
        self.rtsp_socket.send(request.encode())
        print('\nData sent:\n' + request)
        
        # Tính tốc độ video khi Pause hoặc Teardown
        if ((request_code == self.PAUSE and self.state == self.PLAYING) or 
            (request_code == self.TEARDOWN and self.state == self.PLAYING)):
            duration = time.time() - self.play_start_time
            if duration > 0:
                data_rate = int(self.total_bytes_received / duration)
                print(f"[*]Video data rate: {data_rate} bytes/sec")
    
    def receive_rtsp_reply(self):
        """Thread nhận phản hồi RTSP từ server"""
        while True:
            try:
                reply = self.rtsp_socket.recv(1024)
                if reply:
                    self.parse_rtsp_reply(reply.decode("utf-8"))
                
                if self.request_sent == self.TEARDOWN:
                    self.rtsp_socket.shutdown(socket.SHUT_RDWR)
                    self.rtsp_socket.close()
                    break
            except:
                break
    
    def parse_rtsp_reply(self, data):
        """
        Phân tích phản hồi RTSP
        
        Args:
            data: Dữ liệu phản hồi từ server
        """
        lines = data.split('\n')
        try:
            sequence_number = int(lines[1].split(' ')[1])
        except:
            return
        
        if sequence_number == self.rtsp_sequence_number:
            try:
                session = int(lines[2].split(' ')[1])
            except:
                session = self.session_id
            
            if self.session_id == 0:
                self.session_id = session
            
            if self.session_id == session:
                if int(lines[0].split(' ')[1]) == 200:
                    
                    if self.request_sent == self.SETUP:
                        self.state = self.READY
                        self.open_rtp_port()
                        self.play_event.clear()
                        
                        # Khởi động thread nhận RTP
                        if (self.rtp_thread is None) or (not self.rtp_thread.is_alive()):
                            self.rtp_thread = threading.Thread(target=self.listen_rtp, daemon=True)
                            self.rtp_thread.start()
                        
                        print("Auto-starting stream for pre-buffering")
                        self.send_rtsp_request(self.PLAY)
                        self.master.after(100, self.monitor_buffering)
                    
                    elif self.request_sent == self.PLAY:
                        self.state = self.PLAYING
                    
                    elif self.request_sent == self.PAUSE:
                        self.state = self.READY
                    
                    elif self.request_sent == self.TEARDOWN:
                        self.state = self.INIT
                        self.teardown_acknowledged = 1
    
    def open_rtp_port(self):
        """Mở socket UDP để nhận dữ liệu RTP"""
        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.rtp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        except:
            pass
        self.rtp_socket.settimeout(0.5)
        try:
            self.rtp_socket.bind(('', self.rtp_port))
        except:
            tk_message_box.showwarning('Unable to Bind', 
                                      f'Unable to bind PORT={self.rtp_port}')
    
    def handler(self):
        """Xử lý sự kiện đóng cửa sổ"""
        self.pause_movie()
        if tk_message_box.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exit_client()
        else:
            self.play_movie()
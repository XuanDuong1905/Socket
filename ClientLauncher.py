import sys
from tkinter import Tk
from Client import Client

if __name__ == "__main__":
    try:
        # Lấy tham số từ dòng lệnh
        server_address = sys.argv[1]    # IP Server
        server_port = sys.argv[2]       # Port RTSP
        rtp_port = sys.argv[3]          # Port RTP
        filename = sys.argv[4]          # Tên file video
    except:
        # Nếu thiếu tham số thì in hướng dẫn và thoát
        print("[Usage: ClientLauncher.py Server_name Server_port RTP_port Video_file]\n")
        sys.exit(1)
    
    root = Tk()
    
    # Khởi tạo ứng dụng Client với tên biến rõ ràng
    application = Client(root, server_address, server_port, rtp_port, filename)
    
    application.master.title("RTPClient")
    root.mainloop()
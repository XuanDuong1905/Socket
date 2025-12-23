import sys
import socket
from ServerWorker import ServerWorker


class Server:
    """
    RTSP Server - Lắng nghe và chấp nhận kết nối từ client
    """
    
    def main(self):
        """
        Hàm chính để khởi động server
        """
        try:
            server_port = int(sys.argv[1])
        except:
            print("[Usage: Server.py Server_port]\n")
            return
        
        # Tạo socket TCP để lắng nghe kết nối RTSP
        rtsp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rtsp_socket.bind(('', server_port))
        rtsp_socket.listen(5)  # Tối đa 5 kết nối hàng chờ
        
        print(f"RTSP Server started on port {server_port}")
        print("Waiting for client connections...\n")
        
        # Vòng lặp vô hạn chấp nhận kết nối
        while True:
            print("Listening for client...")
            
            client_info = {}
            client_socket, client_address = rtsp_socket.accept()
            
            print(f"Accepted connection from {client_address[0]}:{client_address[1]}")
            
            # Lưu thông tin client
            client_info['rtsp_socket'] = (client_socket, client_address)
            
            # Tạo worker mới để xử lý client này
            ServerWorker(client_info).run()


if __name__ == "__main__":
    Server().main()
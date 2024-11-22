import socket
import os

def start_server(host='0.0.0.0', port=12345):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)  # Listen for up to 5 clients
    print(f"Server is listening on {host}:{port}")

    while True:
        conn, addr = server_socket.accept()
        print(f"Connection established with {addr}")
        
        try:
            # Receive initial connection request
            init_request = conn.recv(1024).decode()
            if init_request != "CONNECT":
                print("Invalid connection request")
                conn.send(b"ERROR: Invalid connection request")
                conn.close()
                continue
            conn.send(b"ACK: Connection established")
            
            # Receive file request
            file_request = conn.recv(1024).decode()
            print(f"Client requested file: {file_request}")
            
            if os.path.exists(file_request):
                conn.send(b"ACK: File found. Sending file...")
                with open(file_request, 'rb') as file:
                    while (chunk := file.read(1024)):
                        conn.send(chunk)
                print("File sent successfully.")
            else:
                conn.send(b"ERROR: File not found")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    start_server()

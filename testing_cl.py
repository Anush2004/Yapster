import socket

def request_file(server_ip='192.168.2.140', port=12345, file_name='shared_file.txt', save_as='received_file.txt'):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, port))
    print(f"Connected to server at {server_ip}:{port}")

    try:
        # Send connection request
        client_socket.send(b"CONNECT")
        response = client_socket.recv(1024)
        response = response.decode()
        if not response.startswith("ACK"):
            print(f"Server response: {response}")
            return
        print("Connection established with server")
        
        # Request file
        client_socket.send(file_name.encode())
        response = client_socket.recv(32)
        # print(response[0:80])
        response = response.decode()
        # print(response[0:80])
        if response.startswith("ERROR"):
            print(f"Server response: {response}")
            return
        print(f"Server response: {response}")
        
        # Receive file
        with open(save_as, 'wb') as file:
            while (data := client_socket.recv(1024)):
                file.write(data)
        print(f"File received and saved as {save_as}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

if __name__ == "__main__":
    request_file(file_name="surprise.mp4", save_as="woohoo_copy.mp4")

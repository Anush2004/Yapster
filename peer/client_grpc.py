import asyncio
import grpc
import time
import sys
import os
pwd = os.getcwd()
pwd = pwd.split('/')
pwd = '/'.join(pwd[:-1])
pwd = pwd + '/protofiles'
sys.path.append(pwd)
import broker_pb2
import broker_pb2_grpc
import aioconsole
import threading
import socket

music_directory = "../music"
port_number = None
class NapsterClient:
    def __init__(self, client_id, server_address='192.168.2.220:4018', music_dir="music"):
        self.client_id = client_id
        self.server_address = server_address
        self.music_dir = music_dir
        self.local_songs = set()
        self.external_songs = set()

    async def heartbeat(self, stub):
        # print("Starting heartbeat function")
        with open('../logs/heartbeat.log', 'w') as f:
            while True:
                # try:
                # print("Sending Heartbeat")
                response = await stub.Heartbeat(broker_pb2.ClientInfo(client_id=self.client_id))
                if response.success:
                    f.write(f"Heartbeat sent for client {self.client_id}.\n")
                else:
                    f.write(f"Heartbeat failed for client {self.client_id}.\n")
                # except Exception as e:
                    # print(f"Error sending heartbeat: {e}")
                f.flush()
                await asyncio.sleep(4)  # Send heartbeat every 5 seconds

    async def initialize_client(self, stub):
        # Load initial songs from the music directory
        self.local_songs = set(os.listdir(self.music_dir))
        
        async def song_update_stream():
            yield broker_pb2.SongUpdate(client_id=self.client_id)
            for song_name in self.local_songs:
                yield broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name)
        try:    
            async for update in stub.InitializeClient(song_update_stream()):
                # print(f"Received update: {update.type} - {update.song_name}")
                if update.type == "error":
                    print(f"Error during initialization: {update.song_name}")
                    return
                if update.type == "add":
                    self.external_songs.add(update.song_name)
        except Exception as e:
            print(f"Error during initialization: {e}\n> ", end="")

    async def leave(self, stub):
        try:
            response = await stub.Leave(broker_pb2.ClientInfo(client_id=self.client_id))
            print(f"Leave response: {response.success}\n> ", end="")
        except Exception as e:
            print(f"Error during leave: {e}\n> ", end="")

    async def add_song(self, stub, song_name):
        try:
            response = await stub.AddSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            print(f"Add song response: {response.message}\n> ", end="")
        except Exception as e:
            print(f"Error adding song: {e}\n> ", end="")

    async def delete_song(self, stub, song_name):
        try:
            response = await stub.DeleteSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            print(f"Delete song response: {response.message}\n> ", end="")
        except Exception as e:
            print(f"Error deleting song: {e}\n> ", end="")

    async def song_request(self, stub, song_name):
        try:
            if song_name in self.local_songs:
                print(f"Song '{song_name}' found in your music directory.\n> ", end="")
                return
            response = await stub.SongRequest(broker_pb2.SongRequestMessage(client_id=self.client_id, song_name=song_name))
            if response.found:
                print(f"Song '{song_name}' found on client: {response.client_id}.\n> ", end="")
                ip_address = response.client_id.split(":")[0]
                port = int(response.client_id.split(":")[1])
                await request_file_from_peer(server_ip=ip_address,port=port,file_name=song_name, save_as=song_name)
            else:
                print(f"Song '{song_name}' not found. Message: {response.message}\n> ", end="")
        except Exception as e:
            print(f"Error requesting song: {e}\n> ", end="")

    async def pull_updates(self, stub):
        with open('../logs/pull_updates.log', 'w') as f:
            try:
                async for update in stub.PullUpdates(broker_pb2.ClientInfo(client_id=self.client_id)):
                    f.write(f"Received update: {update.type} - {update.song_name}\n")
                    f.flush()
                    if(update.type == "add"):
                        self.external_songs.add(update.song_name)
                    elif(update.type == "delete"):
                        self.external_songs.remove(update.song_name)
            except Exception as e:
                f.write(f"Error pulling updates: {e}\n")

    async def monitor_directory(self, stub):
        """Monitors the music directory for changes and synchronizes with the broker."""
        with open('../logs/monitor_directory.log', 'w') as f:
            while True:
                current_songs = set(os.listdir(self.music_dir))
                new_songs = current_songs - self.local_songs
                deleted_songs = self.local_songs - current_songs

                for song in new_songs:
                    await self.add_song(stub, song)
                for song in deleted_songs:
                    await self.delete_song(stub, song)

                self.local_songs = current_songs
                await asyncio.sleep(2)  # Check for changes every 2 seconds
            
    async def command_interface(self, stub):
        """Handles interactive commands from the user."""
        print("Interactive mode started. Type 'help' for a list of commands.")
        while True:
            command = await aioconsole.ainput("> ")  # Await the asynchronous input
            command = command.strip().lower()  # Now strip and lower the input

            if command == "list_mine":
                print("Current songs in your music directory:")
                for song in sorted(self.local_songs):
                    print(f"- {song}")
            elif command == "list_others":
                print("Current songs in the network:")
                for song in sorted(self.external_songs):
                    print(f"- {song}")
            elif command.startswith("request "):
                song_name = command.split(" ", 1)[1]
                await self.song_request(stub, song_name)
            elif command == "help":
                print("Available commands:")
                print("  list_mine      - List all songs in your music directory")
                print("  list_others    - List all songs available in the network")
                print("  request <song> - Request a song from the broker")
                print("  help           - Show this help message")
                print("  exit           - Exit the client")
            elif command == "exit":
                print("Exiting client...")
                await self.leave(stub)
                break
            else:
                print("Unknown command. Type 'help' for a list of commands.")
    
    async def run(self):
        try:
            channel = grpc.aio.insecure_channel(self.server_address)
            stub = broker_pb2_grpc.NapsterServiceStub(channel)

            # Initialize client
            await self.initialize_client(stub)

            # Start other tasks
            task_heartbeat = asyncio.create_task(self.heartbeat(stub))
            task_pull_updates = asyncio.create_task(self.pull_updates(stub))
            task_monitor_directory = asyncio.create_task(self.monitor_directory(stub))
            task_command_interface = asyncio.create_task(self.command_interface(stub))

            await task_command_interface
            os.system(f"sudo ufw delete allow {port_number}/tcp; sudo ufw enable")
            
            task_heartbeat.cancel()
            task_pull_updates.cancel()
            task_monitor_directory.cancel()

            # Optionally wait for tasks to exit cleanly
            await asyncio.gather(task_heartbeat, task_pull_updates, task_monitor_directory, return_exceptions=True)

            # await asyncio.gather(task_command_interface, task_heartbeat, task_pull_updates, task_monitor_directory)

        except grpc.aio.AioRpcError as e:
            print(f"gRPC connection error: {e}\n> ", end="")
        except Exception as e:
            print(f"General error: {e}\n> ", end="")
        finally:
            await channel.close()  # Close the channel manually when done
    
def request_file_from_peer(server_ip='192.168.2.140', port=12345, file_name='shared_file.txt', save_as='received_file.txt'):
    with open('../logs/peer_client.log', 'w') as f:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        f.write(f"Connecting to server at {server_ip}:{port}\n")
        client_socket.connect((server_ip, port))
        f.write(f"Connected to server at {server_ip}:{port}\n")
        f.flush()
    
        try:
        # Send connection request
            client_socket.send(b"CONNECT")
            response = client_socket.recv(1024).decode()
            if not response.startswith("ACK"):            
                print(f"Server response: {response}.Try Again.\n> ", end="")
                return
            f.write("Connection established with server\n")
            f.flush()
            # Request file
            client_socket.send(file_name.encode())
            response = client_socket.recv(32).decode()
            if response.startswith("ERROR"):
                print(f"Server response: {response}.Try Again.\n> ", end="")
                return
            f.write(f"Server response: {response}\n")
            f.flush()
            
            # Receive file
            with open(save_as, 'wb') as file:
                while (data := client_socket.recv(1024)):
                    file.write(data)
        
            print(f"File has been received and saved in your music directory as {save_as}\n> ", end="")
        except Exception as e:
            print(f"Error: {e}.Try Again.\n> ", end="")
        finally:
            client_socket.close()
      
async def handle_peer_requests(reader, writer):
    with open('../logs/peer_server.log', 'w') as f:
        addr = writer.get_extra_info('peername')
        f.write(f"Connection established with {addr}\n")
        f.flush()
        try:
            # Receive initial connection request
            init_request = await reader.read(1024)
            if init_request.decode() != "CONNECT":
                # print("Invalid connection request")
                writer.write(b"ERROR: Invalid connection request")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return
            
            writer.write(b"ACK: Connection established")
            await writer.drain()
        
        # Receive file request
            file_request = await reader.read(1024)
            file_request = os.path.join(music_directory, file_request.decode().strip())
            f.write(f"Client requested file: {file_request}\n")
            f.flush()
        
            if os.path.exists(file_request):
                writer.write(b"ACK: File found. Sending file...")
                await writer.drain()
                
                # Send the file in chunks
                with open(file_request, 'rb') as file:
                    while chunk := file.read(1024):
                        writer.write(chunk)
                        await writer.drain()
                f.write("File sent successfully.\n")
            else:
                writer.write(b"ERROR: File not found")
                await writer.drain()
        except Exception as e:
            print(f"Error: {e}\n>")
        finally:
            writer.close()
            await writer.wait_closed()

async def start_server(host='0.0.0.0', port=12345):
    global port_number
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0)) 
        port_number = s.getsockname()[1] 
    os.system(f"sudo ufw allow {port_number}/tcp; sudo ufw enable")
    # print(f"Server is listening on port {port_number}")
    server = await asyncio.start_server(handle_peer_requests, host, port_number)
    async with server:
        await server.serve_forever()

def start_peer_server():
    asyncio.run(start_server())

def find_ip_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8",80))
            ip_address = s.getsockname()[0]
        return ip_address
    except Exception as e:
        print(f"Error finding IP address: {e}")
        return None
    
if __name__ == "__main__":
    thread = threading.Thread(target = start_peer_server,daemon = True)
    thread.start()
    
    while(port_number == None):
        pass
    # ip address  + port number
    ip_address = find_ip_address()
    client_id = str(ip_address) + ":" + str(port_number)
    
    if not os.path.exists(music_directory):
        print("Music directory not found. Please create a 'music' directory in the current folder.")
        sys.exit(1)


    client = NapsterClient(client_id, music_dir=music_directory)
    asyncio.run(client.run())

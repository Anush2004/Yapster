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
import math  
from collections import defaultdict


demand_lock = threading.Lock()
music_directory = "../music"
port_number = None
current_demand = 0
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
                response = await stub.HeartbeatRequest(broker_pb2.ClientInfo(client_id=self.client_id,demand = current_demand ))
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
            print(f"Error during initialization: {e}")

    async def leave(self, stub):
        try:
            response = await stub.Leave(broker_pb2.ClientInfo(client_id=self.client_id))
            print(f"Leave response: {response.success}", end="")
        except Exception as e:
            print(f"Error during leave: {e}\n> ", end="")

    async def add_song(self, stub, song_name):
        try:
            response = await stub.AddSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            # print(f"Add song response: {response.message}\n> ", end="")
        except Exception as e:
            print(f"Error adding song: {e}\n> ", end="")

    async def delete_song(self, stub, song_name):
        try:
            response = await stub.DeleteSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            # print(f"Delete song response: {response.message}\n> ", end="")
        except Exception as e:
            print(f"Error deleting song: {e}\n> ", end="")
    
    async def request_for_song(self, song_name, response):
        # print(f"Song '{song_name}' found on client: {response.client_id}.\n> ", end="")
        client_dict = dict(eval(response.client_id))
        print(f"Song '{song_name}' found. Requesting file...")
        ip_address = response.client_id.split(":")[0]
        port = int(response.client_id.split(":")[1])
        # print("Going to request")
        request_file_from_peers(server_ip=ip_address,port=port,file_name=song_name, save_as=song_name)
        print("File received successfully")

    async def song_request(self, stub, song_name):
        try:
            if song_name in self.local_songs:
                print(f"Song '{song_name}' found in your music directory")
                return
            response = await stub.SongRequest(broker_pb2.SongRequestMessage(client_id=self.client_id, song_name=song_name))
            if response.found:
                
                
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
                
                f.write(f"Current songs in music directory: {os.listdir(self.music_dir)}\n")
                f.write(f"Current songs in local_songs: {self.local_songs}\n")
                f.flush()

                for song in new_songs:
                    await self.add_song(stub, song)
                    if(song in self.external_songs):
                        self.external_songs.remove(song)
                for song in deleted_songs:
                    await self.delete_song(stub, song)

                self.local_songs = current_songs
                await asyncio.sleep(2)  # Check for changes every 2 seconds
            
    async def command_interface(self, stub):
        """Handles interactive commands from the user."""
        print("Interactive mode started")
        await asyncio.sleep(5) # Sleep for a bit to avoid spamming the console
        print()
        print("Available commands:")
        print("  list_mine      - List all songs in your music directory")
        print("  list_others    - List all songs available in the network")
        print("  request <song> - Request a song from the broker")
        print("  help           - Show this help message")
        print("  exit           - Exit the client")
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
        f.flush()
        client_socket.connect((server_ip, port))
        f.write(f"Connected to server at {server_ip}:{port}\n")
        f.flush()
    
        try:
            client_socket.send(b"CONNECT")
            response = client_socket.recv(1024).decode()
            if not response.startswith("ACK"):            
                print(f"Server response: {response}.Try Again.")
                return
            f.write("Connection established with server\n")
            f.flush()
            # Request file
            client_socket.send(file_name.encode())
            response = client_socket.recv(32).decode()
            if response.startswith("ERROR"):
                print(f"Server response: {response}.Try Again")
                return
            f.write(f"Server response: {response}")
            f.flush()
            
            # Receive file
            save_as = os.path.join(music_directory, save_as)
            with open(save_as, 'wb') as file:
                while (data := client_socket.recv(1024)):
                    file.write(data)
        
            # print(f"File has been received and saved in your music directory as {save_as}\n> ", end="")
        except Exception as e:
            print(f"Error: {e}.Try Again")
        finally:
            client_socket.close()

async def request_metadata(client_info, file_name):
    ip_port, demand = client_info
    if demand >= 100:
        return None  # Skip clients with demand >= 100
    try:
        reader, writer = await asyncio.open_connection(*ip_port.split(':'))
        writer.write(b"METADATA")
        await writer.drain()
        writer.write(file_name.encode())
        await writer.drain()

        response = await asyncio.wait_for(reader.read(1024), timeout=5)  # Timeout for metadata request
        if response.startswith(b"ERROR"):
            return None
        file_size = int(response.decode())
        writer.close()
        await writer.wait_closed()
        return ip_port, file_size
    except Exception as e:
        # print(f"Error requesting metadata from {ip_port}: {e}")
        return None

async def request_file_clipping(client_info, file_name, offset, size, timeout=10):
    ip_port, demand = client_info
    try:
        reader, writer = await asyncio.open_connection(*ip_port.split(':'))
        writer.write(b"REQUEST")
        await writer.drain()
        writer.write(f"{file_name}:{offset}:{size}".encode())
        await writer.drain()

        received_data = b""
        last_receive_time = asyncio.get_event_loop().time()
        while len(received_data) < size:
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=timeout)
                if not chunk:
                    break
                received_data += chunk
                last_receive_time = asyncio.get_event_loop().time()
            except asyncio.TimeoutError:
                if asyncio.get_event_loop().time() - last_receive_time > timeout:
                    raise TimeoutError("Client timed out during file transfer")
        
        writer.close()
        await writer.wait_closed()
        if len(received_data) == size:
            return ip_port, received_data
        else:
            raise ValueError("Incomplete data received")
    except Exception as e:
        print(f"Error requesting file clipping from {ip_port}: {e}")
        return None

async def download_file(clients_dict, file_name):
    save_path = os.path.join(music_directory, file_name)
    client_results = {client: 0 for client in clients_dict.keys()}  # 0 for clients not requested
    metadata_results = await asyncio.gather(
        *(request_metadata(client_info, file_name) for client_info in clients_dict.items())
    )
    metadata_results = [result for result in metadata_results if result is not None]

    # Calculate clippings based on demands
    total_demand = sum(demand for _, demand in clients_dict.items())
    offsets_sizes = {}
    offset =0
    active_addresses = []
    for ip_port, file_size in metadata_results:
        client_demand = clients_dict[ip_port]
        size = math.ceil((client_demand / total_demand) * file_size)
        offsets_sizes[ip_port] = (size, offset)  # size, offset
        offset += size
        active_addresses.append(ip_port)
        # total_demand -= client_demand
        # file_size -= size
    
    # Request file clippings asynchronously
    remaining_data = defaultdict(bytes)
    unattained_files = []
    async def handle_clipping(client_info):
        ip_port, (size, offset) = client_info
        result = await request_file_clipping((ip_port, clients_dict[ip_port]), file_name, offset, size)
        if result is not None:
            ip_port, data = result
            remaining_data[ip_port] = data
            client_results[ip_port] = 1  # File sent completely
        else:
            active_addresses.remove(ip_port)
            client_results[ip_port] = -1  # File not sent completely
            unattained_files.append((size, offset))
            

    await asyncio.gather(*(handle_clipping(info) for info in offsets_sizes.items()))

    # Combine file parts and save
    with open(save_path, 'wb') as f:
        for ip_port in metadata_results:
            if ip_port in remaining_data:
                f.write(remaining_data[ip_port])

    return client_results
     
async def handle_peer_requests(reader, writer):
    with open('../logs/peer_server.log', 'w') as f:
        global current_demand
        addr = writer.get_extra_info('peername')
        f.write(f"Connection established with {addr}\n")
        f.flush()
        try:
            demand_lock.acquire()
            current_demand += 1
            demand_lock.release()
            # Receive initial connection request
            init_request = await reader.read(1024)
            if init_request.decode() != "CONNECT":
                # print("Invalid connection request")
                writer.write(b"ERROR: Invalid connection request")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                demand_lock.acquire()
                current_demand -= 1
                demand_lock.release()
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
            demand_lock.acquire()
            current_demand -= 1
            demand_lock.release()
            print(f"Error: {e}\n>")
        finally:
            writer.close()
            await writer.wait_closed()
            demand_lock.acquire()
            current_demand -= 1
            demand_lock.release()

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

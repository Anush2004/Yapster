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

class NapsterClient:
    def __init__(self, client_id, server_address='192.168.2.220:4018', music_dir="music"):
        self.client_id = client_id
        self.server_address = server_address
        self.music_dir = music_dir
        self.local_songs = set()
        self.external_songs = set()

    async def heartbeat(self, stub):
        # print("Starting heartbeat function")
        with open('logs/heartbeat.log', 'w') as f:
            while True:
                # try:
                # print("Sending Heartbeat")
                response = await stub.Heartbeat(broker_pb2.ClientInfo(client_id=self.client_id))
                if response.success:
                    f.write(f"Heartbeat sent for client {self.client_id}.")
                else:
                    f.write(f"Heartbeat failed for client {self.client_id}.")
                # except Exception as e:
                    # print(f"Error sending heartbeat: {e}")
                await asyncio.sleep(4)  # Send heartbeat every 5 seconds

    async def initialize_client(self, stub):
        # Load initial songs from the music directory
        self.local_songs = set(os.listdir(self.music_dir))
        
        async def song_update_stream():
            yield broker_pb2.SongUpdate(client_id=self.client_id)
            for song_name in self.local_songs:
                # print(song_name)
                yield broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name)
                # await asyncio.sleep(0.1)
        # try:    
        async for update in stub.InitializeClient(song_update_stream()):
            print(f"Received update: {update.type} - {update.song_name}")
            if update.type == "error":
                print(f"Error during initialization: {update.song_name}")
                return
            if update.type == "add":
                self.external_songs.add(update.song_name)
        # except Exception as e:
        #     print(f"Error during initialization: {e}")

    async def leave(self, stub):
        try:
            response = await stub.Leave(broker_pb2.ClientInfo(client_id=self.client_id))
            print(f"Leave response: {response.success}")
        except Exception as e:
            print(f"Error during leave: {e}")

    async def add_song(self, stub, song_name):
        try:
            response = await stub.AddSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            print(f"Add song response: {response.message}")
        except Exception as e:
            print(f"Error adding song: {e}")

    async def delete_song(self, stub, song_name):
        try:
            response = await stub.DeleteSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            print(f"Delete song response: {response.message}")
        except Exception as e:
            print(f"Error deleting song: {e}")

    async def song_request(self, stub, song_name):
        try:
            response = await stub.SongRequest(broker_pb2.SongRequestMessage(client_id=self.client_id, song_name=song_name))
            if response.found:
                print(f"Song '{song_name}' found on client: {response.client_id}.")
            else:
                print(f"Song '{song_name}' not found. Message: {response.message}")
        except Exception as e:
            print(f"Error requesting song: {e}")

    async def pull_updates(self, stub):
        with open('logs/pull_updates.log', 'w') as f:
            try:
                async for update in stub.PullUpdates(broker_pb2.ClientInfo(client_id=self.client_id)):
                    f.write(f"Received update: {update.type} - {update.song_name}")
                    if(update.type == "add"):
                        self.external_songs.add(update.song_name)
                    elif(update.type == "delete"):
                        self.external_songs.remove(update.song_name)
            except Exception as e:
                f.write(f"Error pulling updates: {e}")

    async def monitor_directory(self, stub):
        """Monitors the music directory for changes and synchronizes with the broker."""
        with open('logs/monitor_directory.log', 'w') as f:
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
                print("  list_mine          - List all songs in your music directory")
                print("  list_others       - List all songs available in the network")
                print("  request <song> - Request a song from the broker")
                print("  help          - Show this help message")
                print("  exit          - Exit the client")
            elif command == "exit":
                print("Exiting client...")
                await self.leave(stub)
                break
            else:
                print("Unknown command. Type 'help' for a list of commands.")


    # async def run(self):
    #     async with grpc.aio.insecure_channel(self.server_address) as channel:
    #         stub = broker_pb2_grpc.NapsterServiceStub(channel)

    #         # Initialize client
    #         await self.initialize_client(stub)

    #         # Start the heartbeat in the background
    #         asyncio.create_task(self.heartbeat(stub))

    #         # Start pulling updates in the background
    #         asyncio.create_task(self.pull_updates(stub))

    #         # Monitor the directory for changes
    #         asyncio.create_task(self.monitor_directory(stub))

    #         # Start the interactive command interface
    #         # await self.command_interface(stub)
    
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

            # await task_command_interface
            await asyncio.gather(task_command_interface, task_heartbeat, task_pull_updates, task_monitor_directory)

        except grpc.aio.AioRpcError as e:
            print(f"gRPC connection error: {e}")
        except Exception as e:
            print(f"General error: {e}")
        finally:
            await channel.close()  # Close the channel manually when done



if __name__ == "__main__":
    client_id = input("Enter client ID: ")
    music_directory = "../music"

    if not os.path.exists(music_directory):
        print("Music directory not found. Please create a 'music' directory in the current folder.")
        sys.exit(1)


    client = NapsterClient(client_id, music_dir=music_directory)
    asyncio.run(client.run())

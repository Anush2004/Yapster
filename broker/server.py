import asyncio
import grpc
from collections import defaultdict
import time
import os
import sys
pwd = os.getcwd()
pwd = pwd.split('/')
pwd = '/'.join(pwd[:-1])
pwd = pwd + '/protofiles'
sys.path.append(pwd)
import broker_pb2
import broker_pb2_grpc

class Broker(broker_pb2_grpc.NapsterServiceServicer):
    def __init__(self):
        self.clients = {}  # {client_id: last_heartbeat_time}
        self.client_demands = {}  # {client_id: demand}
        self.songs = defaultdict(list)  # {song_name: [client_id, ...]}
        self.client_queues = defaultdict(asyncio.Queue)  # {client_id: asyncio.Queue}

    async def Heartbeat(self, request, context):
        print(f"Heartbeat received for client {request.client_id}. demand = {request.demand}")
        if request.client_id in self.clients:
            self.clients[request.client_id] = time.time()
            self.client_demands[request.client_id] = request.demand
        else:
            return broker_pb2.Ack(success=False)
        return broker_pb2.Ack(success=True)

    async def InitializeClient(self, request_iterator, context):
        first_message = True
        client_id = None
        print("Initializing client...")
        async for update in request_iterator:
            if first_message:
                # Use the first message to register the client
                print(f"Registering client {update.client_id}")
                client_id = update.client_id
                if client_id in self.clients:
                    yield broker_pb2.Update(type="error", song_name="Client already exists.")
                    return 
                self.clients[client_id] = time.time()
                self.client_queues[client_id] = asyncio.Queue()
                first_message = False
                continue

            # Add the song from the SongUpdate message
            
            if update.song_name:
                if update.song_name not in self.songs:
                    self.songs[update.song_name] = []
                    for id, queue in self.client_queues.items():
                        if id != client_id:
                            await queue.put(broker_pb2.Update(type="add", song_name=update.song_name))
                if client_id not in self.songs[update.song_name]:
                    self.songs[update.song_name].append(client_id)
        if client_id is not None:
            for song, owners in self.songs.items():
                if client_id not in owners:
                    yield broker_pb2.Update(type="add", song_name=song)
        
    
    async def Leave(self, request, context):
        client_id = request.client_id
        if client_id in self.clients:
            del self.clients[client_id]
            del self.client_queues[client_id]
            for song, owners in list(self.songs.items()):
                if client_id in owners:
                    owners.remove(client_id)
                    if not owners:
                        del self.songs[song]
                        for id, queue in self.client_queues.items():
                            if id != client_id:
                                await queue.put(broker_pb2.Update(type="delete", song_name=song))
            print(f"Client {client_id} left.")
            return broker_pb2.Ack(success=True)
        return broker_pb2.Ack(success=False)

    async def SongRequest(self, request, context):
        if request.client_id not in self.clients:
            return broker_pb2.SongResponse(found=False,message="Client not registered.")
        if request.song_name in self.songs:
            client_demand_info = {client: self.client_demands[client] for client in self.songs[request.song_name]}
            return broker_pb2.SongResponse(client_id=str(client_demand_info), found=True, message="Song found.")
        return broker_pb2.SongResponse(found=False,message="Song not found.")

    async def AddSong(self, request, context):
        if request.client_id not in self.clients:
            return broker_pb2.SongUpdateResponse(success=False, message="Client not registered.")
        if request.song_name not in self.songs:
            self.songs[request.song_name] = []
            for client_id, queue in self.client_queues.items():
                if client_id != request.client_id:
                    await queue.put(broker_pb2.Update(type="add", song_name=request.song_name))
                    
        if request.client_id not in self.songs[request.song_name]:
            self.songs[request.song_name].append(request.client_id)
            return broker_pb2.SongUpdateResponse(success=True, message="Song added.")
        
        return broker_pb2.SongUpdateResponse(success=False, message="Song already added.")

    async def DeleteSong(self, request, context):
        if request.song_name in self.songs and request.client_id in self.songs[request.song_name]:
            self.songs[request.song_name].remove(request.client_id)
            if not self.songs[request.song_name]:
                del self.songs[request.song_name]
                for client_id, queue in self.client_queues.items():
                    if client_id != request.client_id:
                        await queue.put(broker_pb2.Update(type="delete", song_name=request.song_name))
            else:
                for client_id, queue in self.client_queues.items():
                    if client_id == request.client_id:
                        await queue.put(broker_pb2.Update(type="add", song_name=request.song_name))        
            return broker_pb2.SongUpdateResponse(success=True, message="Song deleted.")
        return broker_pb2.SongUpdateResponse(success=False, message="Song not found.")

    async def PullUpdates(self, request, context):
        print(f"Pulling updates for client {request.client_id}.")
        while True:
            item = await self.client_queues[request.client_id].get()
            yield item
    
async def cleanup_clients(broker, interval=10, timeout=10):
    while True:
        await asyncio.sleep(interval)
        current_time = time.time()
        inactive_clients = [
            client_id
            for client_id, last_heartbeat in broker.clients.items()
            if current_time - last_heartbeat > timeout
        ]
        for client_id in inactive_clients:
            print(f"Removing client {client_id} due to inactivity.")
            del broker.clients[client_id]
            del broker.client_queues[client_id]
            for song, owners in list(broker.songs.items()):
                if client_id in owners:
                    owners.remove(client_id)
                    if not owners:
                        del broker.songs[song]
                        for id, queue in broker.client_queues.items():
                            if id != client_id:
                                await queue.put(broker_pb2.Update(type="delete", song_name=song))


async def serve():
    try:
        server = grpc.aio.server()
        broker = Broker()
        broker_pb2_grpc.add_NapsterServiceServicer_to_server(broker, server)
        server.add_insecure_port('0.0.0.0:4018')

        # Start the cleanup coroutine
        asyncio.create_task(cleanup_clients(broker))

        print("Server starting on port 4018...")
        await server.start()
        await server.wait_for_termination()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(serve())

"""Room-code internet relay. Run one instance behind a TLS WebSocket proxy."""
import argparse
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from http import HTTPStatus
import json
import os
import secrets
import time
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from race_protocol import PROTOCOL, TRACK_ID, MAX_FRAME, valid_controls, valid_snapshot

ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


@dataclass
class Room:
    host: object
    guest: object=None
    updated: float=0


class RelayHub:
    def __init__(self,max_rooms=100):
        self.rooms={};self.max_rooms=max_rooms
        self.attempts=defaultdict(deque)
        self.connections=0

    async def reply(self,ws,kind,**fields):
        await ws.send(json.dumps(dict(type=kind,**fields),separators=(',',':'),allow_nan=False))

    async def handler(self,ws):
        self.connections+=1
        role=None;room=None;code=None
        try:
            if self.connections>256:
                await self.reply(ws,'error',message='Service is busy. Try again shortly.');return
            first=json.loads(await asyncio.wait_for(ws.recv(),8))
            if not isinstance(first,dict) or first.get('version')!=PROTOCOL or first.get('track')!=TRACK_ID:
                await self.reply(ws,'error',message='Game versions do not match.');return
            role=first.get('type')
            if role=='create':
                if len(self.rooms)>=self.max_rooms:
                    await self.reply(ws,'error',message='All rooms are busy. Try again shortly.');return
                code=''.join(secrets.choice(ALPHABET) for _ in range(8))
                while code in self.rooms:code=''.join(secrets.choice(ALPHABET) for _ in range(8))
                room=Room(host=ws,updated=time.monotonic())
                self.rooms[code]=room
                await self.reply(ws,'created',code=code)
            elif role=='join':
                now=time.monotonic()
                address=ws.remote_address[0] if ws.remote_address else 'unknown'
                attempts=self.attempts[address]
                while attempts and now-attempts[0]>60:attempts.popleft()
                if len(attempts)>=20:
                    await self.reply(ws,'error',message='Too many room attempts. Wait a minute.');return
                attempts.append(now)
                value=first.get('code')
                if not isinstance(value,str) or len(value)>16:
                    await self.reply(ws,'error',message='Enter the 8-character room code.');return
                code=value.replace('-','').replace(' ','').upper()
                room=self.rooms.get(code)
                if room is None:
                    await self.reply(ws,'error',message='Room not found. Check the code or ask your friend to host again.');return
                if room.guest is not None:
                    await self.reply(ws,'error',message='That room already has two players.');room=None;return
                room.guest=ws;room.updated=now
                await self.reply(ws,'joined',code=code)
                await self.reply(room.host,'peer_joined')
            else:
                await self.reply(ws,'error',message='Invalid room request.');return
            window=time.monotonic();count=0
            async for raw in ws:
                now=time.monotonic()
                if now-window>=1:window=now;count=0
                count+=1
                if count>120:await ws.close(1008,'Too many messages');return
                message=json.loads(raw)
                if not isinstance(message,dict):raise ValueError('Invalid game message')
                if role=='create' and message.get('type')=='state' and valid_snapshot(message.get('snapshot')):
                    peer=room.guest
                elif role=='join' and message.get('type')=='input' and valid_controls(message.get('controls')) is not None:
                    peer=room.host
                else:raise ValueError('Invalid game message')
                room.updated=now
                if peer is not None:
                    try:await asyncio.wait_for(peer.send(raw),2)
                    except (ConnectionClosed,TimeoutError):
                        await peer.close(1011,'Connection too slow')
        except (ConnectionClosed,TimeoutError):pass
        except (ValueError,TypeError,UnicodeError,RecursionError):
            try:await self.reply(ws,'error',message='Invalid game message.')
            except ConnectionClosed:pass
        finally:
            self.connections-=1
            if role=='create' and room is not None and self.rooms.get(code) is room:
                self.rooms.pop(code,None)
                if room.guest is not None:
                    try:await self.reply(room.guest,'room_closed')
                    except ConnectionClosed:pass
                    await room.guest.close(1000,'Host left')
            elif role=='join' and room is not None and room.guest is ws:
                room.guest=None
                try:await self.reply(room.host,'peer_left')
                except ConnectionClosed:pass

    async def cleanup(self):
        while True:
            await asyncio.sleep(15)
            now=time.monotonic()
            for code,room in list(self.rooms.items()):
                if now-room.updated>1800:
                    self.rooms.pop(code,None)
                    for peer in (room.host,room.guest):
                        if peer is not None:
                            try:await self.reply(peer,'error',message='Room expired. Host a new race.')
                            except ConnectionClosed:pass
                            await peer.close(1000,'Room expired')
            for address,attempts in list(self.attempts.items()):
                if not attempts or now-attempts[-1]>60:self.attempts.pop(address,None)


def health(connection,request):
    if request.path=='/health':return connection.respond(HTTPStatus.OK,'Apex relay healthy\n')
    if request.path!='/ws':return connection.respond(HTTPStatus.NOT_FOUND,'Not found\n')


async def run(host,port):
    hub=RelayHub()
    async with serve(hub.handler,host,port,process_request=health,max_size=MAX_FRAME,
                     max_queue=8,compression=None,ping_interval=15,ping_timeout=15,
                     close_timeout=2,write_limit=32768) as server:
        print('Relay listening on port',server.sockets[0].getsockname()[1],flush=True)
        cleanup=asyncio.create_task(hub.cleanup())
        try:await server.serve_forever()
        finally:cleanup.cancel()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='0.0.0.0')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','10000')))
    args=parser.parse_args()
    asyncio.run(run(args.host,args.port))

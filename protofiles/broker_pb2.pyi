from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ClientInfo(_message.Message):
    __slots__ = ("client_id",)
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    def __init__(self, client_id: _Optional[str] = ...) -> None: ...

class Ack(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

class SongRequestMessage(_message.Message):
    __slots__ = ("song_name", "client_id")
    SONG_NAME_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    song_name: str
    client_id: str
    def __init__(self, song_name: _Optional[str] = ..., client_id: _Optional[str] = ...) -> None: ...

class SongResponse(_message.Message):
    __slots__ = ("client_id", "found", "message")
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    FOUND_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    found: bool
    message: str
    def __init__(self, client_id: _Optional[str] = ..., found: bool = ..., message: _Optional[str] = ...) -> None: ...

class SongUpdate(_message.Message):
    __slots__ = ("client_id", "song_name")
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    SONG_NAME_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    song_name: str
    def __init__(self, client_id: _Optional[str] = ..., song_name: _Optional[str] = ...) -> None: ...

class Update(_message.Message):
    __slots__ = ("song_name", "type")
    SONG_NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    song_name: str
    type: str
    def __init__(self, song_name: _Optional[str] = ..., type: _Optional[str] = ...) -> None: ...

class SongUpdateResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

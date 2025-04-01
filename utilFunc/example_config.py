import asyncio
import json
import os
import uuid
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, Union, overload, TYPE_CHECKING

"""
This file contains the configuration for the bot, including API tokens and database connection information.
This is just a template and should be modified to suit your needs.
Make sure to keep your tokens and sensitive information secure, i realize this
information could be stored as environment variables or in a secure vault,
but for the sake of simplicity, they are hardcoded here because I was lazy.

In most places requiring a token or database connection, you will need to
import this file and access the variables directly.

This file is setup as i use it, and is normally in the utilFunc directory.
"""

# Discord bot token & github token
TOKEN = "discord bot token"
GITHUB_TOKEN = "github token"

# Open Weather API token
OW_API = "open weather api token"

# Database connection information
DB_NAME = " "
DB_USER = " "
DB_PASSWORD = " "
DB_HOST = " "
DB_PORT = " "
# Test server and channel IDs
TestGuild_ID = 1234567890123456789
TestChannel_ID = 1234567890123456789

if TYPE_CHECKING:
    pass

_T = TypeVar('_T')

ObjectHook = Callable[[Dict[str, Any]], Any]


class Config(Generic[_T]):
    """The "database" object. Internally based on ``json``."""

    def __init__(
            self,
            name: str,
            *,
            object_hook: Optional[ObjectHook] = None,
            encoder: Optional[Type[json.JSONEncoder]] = None,
            load_later: bool = False,
    ):
        self.name = name
        self.object_hook = object_hook
        self.encoder = encoder
        self.loop = asyncio.get_running_loop()
        self.lock = asyncio.Lock()
        self._db: Dict[str, Union[_T, Any]] = {}
        if load_later:
            self.loop.create_task(self.load())
        else:
            self.load_from_file()

    def load_from_file(self):
        try:
            with open(self.name, 'r', encoding='utf-8') as f:
                self._db = json.load(f, object_hook=self.object_hook)
        except FileNotFoundError:
            self._db = {}

    async def load(self):
        async with self.lock:
            await self.loop.run_in_executor(None, self.load_from_file)

    def _dump(self):
        temp = f'{uuid.uuid4()}-{self.name}.tmp'
        with open(temp, 'w', encoding='utf-8') as tmp:
            json.dump(self._db.copy(), tmp, ensure_ascii=True, cls=self.encoder, separators=(',', ':'))

        # atomically move the file
        os.replace(temp, self.name)

    async def save(self) -> None:
        async with self.lock:
            await self.loop.run_in_executor(None, self._dump)

    @overload
    def get(self, key: Any) -> Optional[Union[_T, Any]]:
        ...

    @overload
    def get(self, key: Any, default: Any) -> Union[_T, Any]:
        ...

    def get(self, key: Any, default: Any = None) -> Optional[Union[_T, Any]]:
        """Retrieves a config entry."""
        return self._db.get(str(key), default)

    async def put(self, key: Any, value: Union[_T, Any]) -> None:
        """Edits a config entry."""
        self._db[str(key)] = value
        await self.save()

    async def remove(self, key: Any) -> None:
        """Removes a config entry."""
        del self._db[str(key)]
        await self.save()

    def __contains__(self, item: Any) -> bool:
        return str(item) in self._db

    def __getitem__(self, item: Any) -> Union[_T, Any]:
        return self._db[str(item)]

    def __len__(self) -> int:
        return len(self._db)

    def all(self) -> Dict[str, Union[_T, Any]]:
        return self._db

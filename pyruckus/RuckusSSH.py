"""Ruckus SSH client."""
from asyncio import sleep
import paramiko

from .const import (
    CMD_CONFIG,
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_ENABLE_FORCE,
    CMD_END,
    CMD_QUIT,
    CONNECT_ERROR_EOF,
    CONNECT_ERROR_PRIVILEGED_ALREADY_LOGGED_IN,
    CONNECT_ERROR_TIMEOUT,
    LOGIN_ERROR_LOGIN_INCORRECT,
    PROMPT
)
from .exceptions import AuthenticationError


class RuckusSSH():
    """Ruckus SSH client."""

    def __init__(
        self,
        timeout=30
    ) -> None:
        """Ruckus SSH client constructor."""
        self._timeout = timeout
        self._cli = None
        self._client = None
        self._root_mode = False
        self._isalive = True

    async def login(
        self, host: str, port: int, username=None, password="", login_timeout=10
    ) -> bool:
        """Log into the Ruckus device."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, port=port)
        cli = client.invoke_shell()
        cli.settimeout(self._timeout)
        start = 0
        while True:
            data = cli.recv(128).decode()
            if "Please login:" in data:
                break
            await sleep(1)
            start = start + 1
            if start > login_timeout:
                return False

        # login with username
        cli.send(f"{str(username).strip()}\n")
        while not cli.recv_ready():
            await sleep(0.2)
        start = 0
        while True:
            data = cli.recv(128).decode()
            if "Password:" in data:
                break
            await sleep(1)
            start = start + 1
            if start > login_timeout:
                raise ConnectionError(CONNECT_ERROR_TIMEOUT)

        # password
        cli.send(f"{str(password).strip()}\n")
        while not cli.recv_ready():
            await sleep(0.2)
        start = 0
        while True:
            data = cli.recv(256).decode()
            if LOGIN_ERROR_LOGIN_INCORRECT in data:
                raise ConnectionError(LOGIN_ERROR_LOGIN_INCORRECT)
            for value in PROMPT:
                if value in data:
                    self._cli = cli
                    self._client = client
                    self._isalive = True
                    return self._isalive
            await sleep(1)
            start = start + 1
            if start > login_timeout:
                raise ConnectionError(CONNECT_ERROR_TIMEOUT)

        return False

    def close(self) -> None:
        """Close the client."""
        self._client.close()

    async def run(self, cmd: str, nbytes=1024) -> str:
        """Run a command."""
        cli = self._cli
        cli.send(f"{str(cmd).strip()}\n")
        while not cli.recv_ready():
            await sleep(0.2)
        start = 0
        result = ""
        while True:
            data = cli.recv(nbytes).decode('utf-8', 'ignore')
            result = result + data
            if cli.recv_ready():
                start = 0
            for value in PROMPT:
                if value in data:
                    return result.replace(value, "")
            await sleep(1)
            start = start + 1
            if start > self._timeout:
                return result

    async def run_privileged(self, cmd: str, nbytes=1024) -> str:
        """Run a privileged command."""
        await self.enable(force=True)
        result = await self.run(cmd, nbytes=nbytes)
        await self.disable()
        return result

    async def enable(self, force=False) -> None:
        """Enable privileged commands."""
        if force:
            cmd = f"{CMD_ENABLE} {CMD_ENABLE_FORCE}"
        else:
            cmd = CMD_ENABLE

        result = await self.run(cmd)
        if CONNECT_ERROR_PRIVILEGED_ALREADY_LOGGED_IN in result:
            raise ConnectionError(CONNECT_ERROR_PRIVILEGED_ALREADY_LOGGED_IN)
        self._root_mode = True

    async def disable(self) -> None:
        """Disable privileged commands."""
        await self.run(CMD_DISABLE)

    async def config(self, force=False) -> None:
        """Go to config mode"""
        if not self._root_mode:
            await self.enable(force)
        await self.run(CMD_CONFIG)

    async def end(self) -> None:
        """ end/exit config """
        if self._root_mode:
            await self.run(CMD_END)

    async def quit(self) -> None:
        """ quit """
        if self._root_mode:
            await self.run(CMD_END)
        self._cli.send(f"{str(CMD_QUIT).strip()}\n")

    def isalive(self) -> bool:
        """ is alive"""
        return self._isalive

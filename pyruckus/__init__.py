"""The main pyruckus API class."""
from .const import (
    CMD_ADD_MAC,
    CMD_AP_INFO,
    CMD_CURRENT_ACTIVE_CLIENTS,
    CMD_DEL_MAC,
    CMD_L2ACL,
    CMD_MESH_INFO,
    CMD_SHOW_CONFIG,
    CMD_SHOW_L2ACL,
    CMD_SYSTEM_INFO,
    CMD_WLAN,
    HEADER_LAST_EVENTS,
    MESH_NAME_ESSID,
    MESH_SETTINGS,
)
from .response_parser import parse_ruckus_key_value
from .RuckusSSH import RuckusSSH


class Ruckus:
    """Class for communicating with the device."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port=22,
        login_timeout=15,
        timeout=10,
    ) -> None:
        """Set runtime configuration."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.login_timeout = login_timeout
        self.timeout = timeout

        self.ssh = None

    def __del__(self) -> None:
        """Disconnect on delete."""
        self.disconnect()

    @staticmethod
    async def create(
        host: str, username: str, password: str, port=22, login_timeout=15, timeout=10
    ) -> "Ruckus":
        """Create a new Ruckus object and connect."""
        ruckus = Ruckus(
            host,
            username,
            password,
            port=port,
            login_timeout=login_timeout,
            timeout=timeout,
        )
        await ruckus.connect()
        return ruckus

    async def connect(self) -> bool:
        """Create SSH connection and login."""
        ssh = RuckusSSH()
        result = await ssh.login(
            self.host,
            self.port,
            username=self.username,
            password=self.password,
            login_timeout=self.login_timeout,
        )
        self.ssh = ssh
        return result

    def disconnect(self) -> None:
        """Close the SSH session."""
        if self.ssh and self.ssh.isalive():
            self.ssh.close()

    async def ensure_connected(self) -> bool:
        """Make sure we are connected to SSH. Reconnects if disconnected."""
        if self.ssh and self.ssh.isalive():
            return True
        return await self.connect()

    async def run_and_parse(self, cmd: str, partition=None, nbytes=1024) -> dict:
        """Run a command and parse the response."""
        await self.ensure_connected()
        result = await self.ssh.run_privileged(cmd, nbytes=nbytes)
        if partition:
            result = result.partition(partition)[0]
        return parse_ruckus_key_value(result)

    async def mesh_info(self) -> dict:
        """Pull the current mesh name."""
        return await self.run_and_parse(CMD_MESH_INFO)

    async def mesh_name(self) -> str:
        """Pull the current mesh name."""
        try:
            mesh_info = await self.mesh_info()
            return mesh_info[MESH_SETTINGS][MESH_NAME_ESSID]
        except KeyError:
            return "Ruckus Mesh"

    async def system_info(self) -> dict:
        """Pull the system info."""
        return await self.run_and_parse(CMD_SYSTEM_INFO)

    async def current_active_clients(self) -> dict:
        """Pull active clients from the device."""
        return await self.run_and_parse(
            CMD_CURRENT_ACTIVE_CLIENTS, partition=HEADER_LAST_EVENTS, nbytes=9216
        )

    async def ap_info(self) -> dict:
        """Pull info about current access points."""
        return await self.run_and_parse(CMD_AP_INFO)

    async def show_config(self) -> dict:
        """Pull all config info. WARNING: this one is slow."""
        return await self.run_and_parse(CMD_SHOW_CONFIG, nbytes=9216)

    async def l2acl_info(self) -> dict:
        """Pull L2ACL info."""
        return await self.run_and_parse(CMD_SHOW_L2ACL)

    async def wlan_info(self) -> dict:
        """Pull WLAN info."""
        return await self.run_and_parse(CMD_WLAN, nbytes=9216)

    async def l2acl(self, name, mode="deny") -> bool:
        """Create L2ACL """
        await self.ssh.config(force=True)
        result = await self.l2acl_info()
        if len(result) >= 1 and "l2_mac_acl" in result:
            acl_id = result["l2_mac_acl"].get("id", {})
            for _key, val in acl_id.items():
                if name == val["name"]:
                    await self.ssh.end()
                    return False
        await self.ssh.run("{} {}".format(CMD_L2ACL, name))
        await self.ssh.run("mode {}".format(mode))
        await self.ssh.end()
        return True

    async def no_l2acl(self, name) -> bool:
        """Remove L2ACL """
        await self.ssh.config()
        await self.ssh.run("no {} {}".format(CMD_L2ACL, name))
        await self.ssh.end()
        return True

    async def l2acl_add_mac(self, name, mac) -> bool:
        """Add Mac address to L2ACL """
        await self.ssh.config(force=True)
        result = await self.l2acl_info()
        if len(result) >= 1 and "l2_mac_acl" in result:
            acl_id = result["l2_mac_acl"].get("id", {})
            for _key, val in acl_id.items():
                if name == val["name"]:
                    await self.ssh.run("{} {}".format(CMD_L2ACL, name))
                    result = await self.ssh.run("{} {}".format(CMD_ADD_MAC, mac))
                    await self.ssh.end()
                    return True
        return False

    async def l2acl_del_mac(self, name, mac) -> bool:
        """Del Mac address to L2ACL """
        await self.ssh.config(force=True)
        result = await self.l2acl_info()
        if len(result) >= 1 and "l2_mac_acl" in result:
            acl_id = result["l2_mac_acl"].get("id", {})
            for _key, val in acl_id.items():
                if name == val["name"]:
                    await self.ssh.run("{} {}".format(CMD_L2ACL, name))
                    result = await self.ssh.run("{} {}".format(CMD_DEL_MAC, mac))
                    await self.ssh.end()
                    return True
        return False
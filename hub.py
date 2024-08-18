"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import json
import logging
import random
from time import time
import urllib.parse

import httpx
import requests

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class Hub:
    """Hub test."""

    manufacturer = "xcp-ng"

    def __init__(self, hass, host):
        """Init."""
        self._host = host
        self._hass = hass
        self._name = host
        self._id = host.lower()
        self._opaque_ref = ''
        self.vms = []
        self.cdomains = []
        self.all_vms = {}
        self.vm_by_uuid = {}
        self.vmis = {}
        self.online = False
        self.pool = {}
        self.pool_opref = ''
        self.host = Host(self)

    @property
    def hub_id(self) -> str:
        """Hub id."""
        return self._id

    @property
    def opref(self):
        """Return opref."""
        return self._opaque_ref

    async def http_req(self, method, path, **kwargs):
        """Http request to xenserver."""
        async with httpx.AsyncClient(verify=False) as client:
            if method == "POST":
                r = await client.post(f"https://{self._host}/{path}", kwargs.get('data', {}), timeout=30.0)
            elif method == "GET":
                r = await client.get(f"https://{self._host}/{path}", timeout=30.0)
        return r

    async def xenapi_rpc(self, data):
        """Json rpc request to xenserver."""
        data["id"] = "ha_xen_connect"
        data["jsonrpc"] = "2.0"
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(f"https://{self._host}/jsonrpc", json=data, timeout=60.0)
        return r

    def log(self, data):
        """Log."""
        _LOGGER.info(data)

    async def authenticate(self, username, password):
        """Auth."""
        req_data = {
            'method': 'session.login_with_password',
            'params': [ username, password ]
        }
        r = await self.xenapi_rpc(req_data)

        res = r.json()
        self._opaque_ref = res['result']
        # _LOGGER.info(f"RES : {r.status_code} : {self._opaque_ref}")
        if r.status_code == 200:
            return True
        return False

    async def get_vmis(self):
        """Get all the vms."""
        req_data = {"jsonrpc":"2.0","method":"VM.get_all_records","params":[self._opaque_ref]}
        r = await self.xenapi_rpc(req_data)
        res = r.json()
        vms = res['result']
        for opref in vms:
            if not vms[opref]["is_a_template"]:
                # self.log(opref)
                self.vmis[opref] = vms[opref]

        return self.vmis

    async def get_vms(self):
        """Get all the vms."""
        vms = await self.get_vmis()
        for opref in vms:
            self.vm_by_uuid[vms[opref]["uuid"]] = VirtualMachine(opref, vms[opref], self)
            self.all_vms[opref] = self.vm_by_uuid[vms[opref]["uuid"]]
            if vms[opref]["is_control_domain"]:
                self.cdomains.append(self.vm_by_uuid[vms[opref]["uuid"]])
            else:
                self.vms.append(self.vm_by_uuid[vms[opref]["uuid"]])

        return self.vm_by_uuid

    async def get_pool(self):
        """Get Pool Info."""
        req_data = {"jsonrpc":"2.0","method":"pool.get_all_records","params":[self._opaque_ref]}
        r = await self.xenapi_rpc(req_data)
        r = r.json()["result"]
        self.pool_opref = list(r.keys())[0]
        self.pool = r[self.pool_opref]
        self.log(f"POOL: {self.pool_opref}")

    async def reloadVms(self, user, password):
        """Reload VM Data."""
        await self.authenticate(user, password)
        await self.get_pool()
        await self.get_vms()
        await self.host.start_host()

    async def test_connection(self) -> bool:
        """Test the connetion."""
        return False


class Host:
    """Control virtual machines."""

    def __init__(self, hub):
        """Initlize."""
        self._hub = hub
        self._loop = asyncio.get_event_loop()
        self._eve_token = None
        self._current_event = {}
        self._current_rrd = {}
        self._is_sync_eve_running = False
        self._is_sync_rrd_running = False
        self._is_sync_vmis_running = False
        self._vms = {}
        self.log("HUB INITLIZED")

    def log(self, data):
        """Log."""
        _LOGGER.info(f"HOST: {data}")

    @property
    def eve_token(self):
        """Return eve token."""
        return self._eve_token

    async def set_eve_token(self):
        """Set event token."""
        req_data = {"method":"event.inject","params":[self._hub.opref, "pool", self._hub.pool_opref]}
        r = await self._hub.xenapi_rpc(req_data)
        self._eve_token = r.json()["result"]

    async def start_host(self):
        """Start Host Monotring."""
        self.log("STARTING HOST")
        if not self._is_sync_eve_running:
            self._loop.create_task(self.sync_events())
        if not self._is_sync_rrd_running:
            self._loop.create_task(self.sync_rrd())
        if not self._is_sync_vmis_running:
            self._loop.create_task(self.sync_vmis())


    async def sync_vmis(self):
        """Sync the Events."""
        self._is_sync_vmis_running = True
        # self.log("Sync: VMS")
        await self._hub.get_vmis()
        await self.update_vmis()
        await asyncio.sleep(5)
        self._loop.create_task(self.sync_vmis())

    async def update_vmis(self):
        """Update all vms with hub.all_vms."""
        await self.publish_update_to_vm()

    async def sync_events(self):
        """Sync the Events."""
        self._is_sync_eve_running = True
        # self.log("Sync: Events")
        if not self.eve_token:
            await self.set_eve_token()
        req_data = {"method":"event.from","params":[self._hub.opref, ["pool", "host", "vm", "sr", "vm_metrics", "host_metrics"], self.eve_token, 5.001]}
        r = await self._hub.xenapi_rpc(req_data)
        # self.log(r.text)
        if r.status_code == 200:
            await self.set_events(r.json()["result"])
            await asyncio.sleep(5)
            self._loop.create_task(self.sync_events())
        else:
            self.log("FAILED SYNC EVENTS")

    @property
    def rrd_time(self):
        """Get rrd time 595 sec before the current time."""
        return int(time()) - 595

    async def sync_rrd(self):
        """Sync RRD."""
        self._is_sync_rrd_running = True
        # self.log("Sync: RRD")
        path = f"rrd_updates?cf=AVERAGE&host=true&interval=5&json=true&start={self.rrd_time}&session_id={urllib.parse.quote(self._hub.opref)}"
        r = await self._hub.http_req("GET", path)
        # self.log(r.text)
        if r.status_code == 200:
            await self.set_rrd_data(r.text)
            # await self.set_rrd_data(r.json())
            await asyncio.sleep(5)
            self._loop.create_task(self.sync_rrd())
        else:
            self.log("FAILED SYNC RRD")
            self.log(r.text)

    async def set_events(self, eve):
        """Set Events."""
        self._current_event = eve
        await self.publish_update_to_vm()

    async def set_rrd_data(self, rrd):
        """Set Events."""
        self._current_rrd = rrd
        await self.publish_update_to_vm()

    async def publish_update_to_vm(self):
        """Publish update too all the sensor/switch."""
        for opref in self._hub.all_vms:
            await self._hub.all_vms[opref].on_vmi_update(self._hub.vmis[opref])
            await self._hub.all_vms[opref].publish_update()


class VirtualMachine:
    """Virtual Machine info."""

    def __init__(self, opref, vmi, hub):
        """Init."""
        self._opref = opref
        self._vmi = vmi
        self._id = vmi["uuid"]
        self.name = vmi["name_label"]
        self._power_state = vmi["power_state"]
        self._loop = asyncio.get_event_loop()
        self.hub = hub
        self._callbacks = set()
        self._is_host_called = False
        self._host = self.hub.host

    def log(self, data):
        """Log."""
        _LOGGER.info(f"VM_{self.vm_id}: {data}")

    @property
    def opref(self):
        """Retun opref."""
        return self._opref

    @property
    def vm_id(self):
        """Return VM UUID."""
        return self._vmi["uuid"]

    @property
    def status(self):
        """Return Power State of VM."""
        return self._vmi["power_state"]

    async def register_callback(self, callback):
        """Add callbacks for sensors/switchs to update."""
        self.log("Registing callback")
        # if not self._is_host_called:
        #     self.log("Calling Hosts")
        #     await self.hub.host.start_host()
        #     self._is_host_called = True

        self._callbacks.add(callback)
        self.log("CallBack Registered.")

    def remove_callback(self, callback):
        """Remove callbacks for sensors/switchs to update."""
        self._callbacks.discard(callback)

    async def start(self):
        """"Start the VM."""
        req_data = {"method":"VM.start","params":[self.hub.opref, self._opref, False, False]}
        r = await self.hub.xenapi_rpc(req_data)

    async def stop(self):
        """Stop the VM."""
        req_data = {"method":"VM.clean_shutdown","params":[self.hub.opref, self._opref]}
        r = await self.hub.xenapi_rpc(req_data)

    async def on_vmi_update(self, vmi_data):
        """Update all the VM Data Update."""
        self._vmi = vmi_data

    async def on_host_update(self):
        """Update all the VM Data."""
        await self.publish_update()

    async def publish_update(self):
        """Publish update too all the sensor/switch."""
        for callback in self._callbacks:
            callback()

    async def update(self):
        """Update the vm stats."""
        req_data = {"jsonrpc":"2.0","method":"VM.get_record","params":[self.hub.opref, self.opref]}
        r = await self.hub.xenapi_rpc(req_data)
        self._vmi = r.json()['result']


class ControlDomain(VirtualMachine):
    """XenHost Domain."""

    def __init__(self, opref, vmi, hub):
        """Initlize Host."""
        super().__init__(opref, vmi, hub)


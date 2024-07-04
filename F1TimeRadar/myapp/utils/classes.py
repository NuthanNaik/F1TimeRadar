from json import dumps, loads
import requests
from urllib.parse import urlparse, urlencode, urlunparse
import asyncio
import websockets
import concurrent.futures
import time, datetime
from myapp.utils.format_data import format_data


# _events.py
class EventHook(object):
    def __init__(self):
        self._handlers = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def __isub__(self, handler):
        self._handlers.remove(handler)
        return self

    async def fire(self, *args, **kwargs):
        for handler in self._handlers:
            await handler(*args, **kwargs)


# _hub.py
class Hub:
    def __init__(self, name, connection):
        self.name = name
        self.server = HubServer(name, connection, self)
        self.client = HubClient(name, connection)


class HubServer:
    def __init__(self, name, connection, hub):
        self.name = name
        self.__connection = connection
        self.__hub = hub

    def invoke(self, method, *data):
        message = {
            'H': self.name,
            'M': method,
            'A': data,
            'I': self.__connection.increment_send_counter()
        }
        self.__connection.send(message)


class HubClient(object):
    def __init__(self, name, connection):
        self.name = name
        self.__handlers = {}

        async def handle(**data):
            messages = data['M'] if 'M' in data and len(data['M']) > 0 else {}
            for inner_data in messages:
                hub = inner_data['H'] if 'H' in inner_data else ''
                if hub.lower() == self.name.lower():
                    method = inner_data['M']
                    message = inner_data['A']
                    await self.__handlers[method](message)

        connection.received += handle

    def on(self, method, handler):
        if method not in self.__handlers:
            self.__handlers[method] = handler

    def off(self, method, handler):
        if method in self.__handlers:
            self.__handlers[method] -= handler


# _parameters.py
class WebSocketParameters:
    def __init__(self, connection):
        self.protocol_version = '1.5'
        self.raw_url = self._clean_url(connection.url)
        self.conn_data = self._get_conn_data()
        self.session = connection.session
        self.headers = None
        self.socket_conf = None
        self._negotiate()
        self.socket_url = self._get_socket_url()

    @staticmethod
    def _clean_url(url):
        if url[-1] == '/':
            return url[:-1]
        else:
            return url

    @staticmethod
    def _get_conn_data():
        conn_data = dumps([{'name': 'streaming'}])
        return conn_data

    @staticmethod
    def _format_url(url, action, query):
        string = '{url}/{action}?{query}'.format(url=url, action=action, query=query)
        print(string)
        return string

    def _negotiate(self):
        if self.session is None:
            self.session = requests.Session()
        query = urlencode({
            'connectionData': self.conn_data,
            'clientProtocol': self.protocol_version,
        })
        url = self._format_url(self.raw_url, 'negotiate', query)
        self.headers = dict(self.session.headers)
        request = self.session.get(url)
        self.headers['Cookie'] = self._get_cookie_str(request.cookies)
        self.socket_conf = request.json()

    @staticmethod
    def _get_cookie_str(request):
        return '; '.join([
            '%s=%s' % (name, value)
            for name, value in request.items()
        ])

    def _get_socket_url(self):
        ws_url = self._get_ws_url_from()
        query = urlencode({
            'transport': 'webSockets',
            'connectionToken': self.socket_conf['ConnectionToken'],
            'connectionData': self.conn_data,
            'clientProtocol': self.socket_conf['ProtocolVersion'],
        })
        return self._format_url(ws_url, 'connect', query)

    def _get_ws_url_from(self):
        parsed = urlparse(self.raw_url)
        scheme = 'wss' if parsed.scheme == 'https' else 'ws'
        url_data = (scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        return urlunparse(url_data)


# _queue_events.py
class Event:
    """Event is base class providing an interface
        for all subsequent(inherited) events."""


class InvokeEvent(Event):
    def __init__(self, message):
        self.type = 'INVOKE'
        self.message = message


class CloseEvent(Event):
    def __init__(self):
        self.type = 'CLOSE'


# _transport.py
class Transport:
    def __init__(self, connection):
        self._connection = connection
        self._ws_params = None
        self._conn_handler = None
        self.ws_loop = None
        self.invoke_queue = None
        self.ws = None
        self._set_loop_and_queue()

    def _set_loop_and_queue(self):
        try:
            self.ws_loop = asyncio.get_event_loop()
        except RuntimeError:
            self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.invoke_queue = asyncio.Queue()

    def start(self):
        self._ws_params = WebSocketParameters(self._connection)
        self._connect()
        if not self.ws_loop.is_running():
            self.ws_loop.run_forever()

    def close(self):
        asyncio.Task(self.invoke_queue.put(CloseEvent()), loop=self.ws_loop)

    def send(self, message):
        asyncio.Task(self.invoke_queue.put(InvokeEvent(message)), loop=self.ws_loop)

    def _connect(self):
        self._conn_handler = asyncio.ensure_future(self._socket(self.ws_loop), loop=self.ws_loop)

    async def _socket(self, loop):
        async with websockets.connect(self._ws_params.socket_url, extra_headers=self._ws_params.headers,
                                      loop=loop) as self.ws:
            self._connection.started = True
            await self._master_handler(self.ws)

    async def _master_handler(self, ws):
        consumer_task = asyncio.ensure_future(self._consumer_handler(ws), loop=self.ws_loop)
        producer_task = asyncio.ensure_future(self._producer_handler(ws), loop=self.ws_loop)
        done, pending = await asyncio.wait([consumer_task, producer_task],
                                           return_when=asyncio.FIRST_EXCEPTION)

        for task in pending:
            task.cancel()

    async def _consumer_handler(self, ws):
        while True:
            message = await ws.recv()
            if len(message) > 0:
                data = loads(message)
                await self._connection.received.fire(**data)

    async def _producer_handler(self, ws):
        while True:
            try:
                event = await self.invoke_queue.get()
                if event is not None:
                    if event.type == 'INVOKE':
                        await ws.send(dumps(event.message))
                    elif event.type == 'CLOSE':
                        await ws.close()
                        while ws.open is True:
                            await asyncio.sleep(0.1)
                        else:
                            self._connection.started = False
                            break
                else:
                    break
                self.invoke_queue.task_done()
            except Exception as e:
                raise e


# _connection.py
class Connection(object):
    protocol_version = '1.5'

    def __init__(self, url, session=None):
        self.url = url
        self.__hubs = {}
        self.__send_counter = -1
        self.hub = None
        self.session = session
        self.received = EventHook()
        self.error = EventHook()
        self.__transport = Transport(self)
        self.started = False

        async def handle_error(**data):
            error = data["E"] if "E" in data else None
            if error is not None:
                await self.error.fire(error)

        self.received += handle_error

    def start(self):
        self.__transport.start()

    def close(self):
        self.__transport.close()

    def increment_send_counter(self):
        self.__send_counter += 1
        return self.__send_counter

    def send(self, message):
        self.__transport.send(message)

    def register_hub(self, name):
        if name not in self.__hubs:
            if self.started:
                raise RuntimeError(
                    'Cannot create new hub because connection is already started.')
            self.__hubs[name] = Hub(name, self)
            return self.__hubs[name]


class SignalRClient:
    _connection_url = 'https://livetiming.formula1.com/signalr'

    def __init__(self, logger):
        self.headers = {'User-agent': 'BestHTTP',
                        'Accept-Encoding': 'gzip, identity',
                        'Connection': 'keep-alive, Upgrade'}
        self.topics = ["Heartbeat", "CarData.z", "Position.z",
                       "ExtrapolatedClock", "TopThree", "RcmSeries",
                       "TimingStats", "TimingAppData",
                       "WeatherData", "TrackStatus", "DriverList",
                       "RaceControlMessages", "SessionInfo",
                       "SessionData", "LapCount", "TimingData"]
        self.debug = True
        self.filename = "output.txt"
        self.filemode = 'w'
        self.timeout = 1800
        self._connection = None
        self.logger = logger
        self._output_file = None
        self.t_last_message = None

    async def _supervise(self):
        self.t_last_message = time.time()
        while True:
            if (self.timeout != 0
                    and time.time() - self.t_last_message > self.timeout):
                print("timeout...")
                self._connection.close()
                return
            await asyncio.sleep(1)

    def _to_file(self, msg):
        if msg == "{}":
            print("Nothing Received", datetime.datetime.now())
            return
        else:
            print(msg, datetime.datetime.now())
            self.t_last_message = time.time()
        self._output_file.write(msg + '\n')
        self._output_file.flush()
    
    def _data_handler(self, msg):
        format_data(msg)

    async def _on_debug(self, **data):
        # print(data)
        if 'M' in data and len(data['M']) > 0:
            self._t_last_message = time.time()

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            # await loop.run_in_executor(
            #     pool, self._to_file, str(data)
            # )
            await loop.run_in_executor(
                pool, self._data_handler, str(data)
            )

    async def _on_do_nothing(self, msg):
        pass

    async def _run(self):
        self._output_file = open(self.filename, self.filemode)
        session = requests.Session()
        session.handlers = self.headers
        self._connection = Connection(self._connection_url, session=session)
        hub = self._connection.register_hub('streaming')
        self._connection.error += self._on_debug
        self._connection.received += self._on_debug
        hub.client.on('feed', self._on_do_nothing)
        hub.server.invoke("subscribe", self.topics)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, self._connection.start)

    async def _async_start(self):
        print("starting live timing client...")
        await asyncio.gather(asyncio.ensure_future(self._supervise()),
                             asyncio.ensure_future(self._run()))
        self._output_file.close()
        print("exiting...")

    def start(self):
        try:
            asyncio.run(self._async_start())
        except KeyboardInterrupt:
            self.logger.warning("Keyboard Interrupt - exiting...")
            return

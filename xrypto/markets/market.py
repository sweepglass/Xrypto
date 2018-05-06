# Copyright (C) 2017, Philsong <songbohr@gmail.com>
# Copyright (C) 2018, geektau <geektau@gmail.com>

import time

import logging
import threading
from decimal import Decimal
import config


class Market(object):
    def __init__(self, pair_code, fee_rate):
        self.name = self.__class__.__name__

        market_currency, base_currency = pair_code.split('_')

        self.base_currency = base_currency.upper()
        self.market_currency = market_currency.upper()

        self.pair_code = pair_code
        self.fee_rate = fee_rate

        self.depth_updated = 0
        self.update_rate = 3

        self.is_terminated = False
        self.request_timeout = 10 #5s
        self.depth = {
            'asks': [{'price': Decimal('0'), 'amount': Decimal('0')}],
            'bids': [{'price': Decimal('0'), 'amount': Decimal('0')}]
        }
        self.kline = None
                
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def terminate(self):
        self.is_terminated = True

    def get_depth(self):
        timediff = time.time() - self.depth_updated
        # logging.warn('Market: %s order book1:(%s>%s)', self.name, timediff, self.depth_updated)
        if timediff > self.update_rate:
            logging.debug('%s should update...', self.name)
            if not self.ask_update_depth():
                return None
        
        timediff = time.time() - self.depth_updated
        # logging.warn('Market: %s order book2:(%s>%s)', self.name, timediff, self.depth_updated)

        if timediff > config.market_expiration_time:
            # logging.warn('Market: %s order book is expired(%s>%s)', self.name, timediff, config.market_expiration_time)
            return None
        return self.depth

    def subscribe_depth(self):
        if config.SUPPORT_ZMQ:
            t = threading.Thread(target = self.subscribe_zmq_depth)
            t.start()  
        elif config.SUPPORT_WEBSOCKET:
            t = threading.Thread(target = self.subscribe_websocket_depth)
            t.start()
        else:
            pass

    def subscribe_zmq_depth(self):
        import exchanges.push as push

        push_s = push.Push(config.ZMQ_PORT)
        push_s.msg_server()

    def subscribe_websocket_depth(self):
        import json
        from socketIO_client import SocketIO

        def on_message(data):
            data = data.decode('utf8')
            if data[0] != '2':
                return

            data = json.loads(data[1:])
            depth = data[1]

            logging.debug("depth coming: %s", depth['market'])
            self.depth_updated = int(depth['timestamp']/1000)
            self.depth = self.format_depth(depth)
        
        def on_connect():
            logging.info('[Connected]')

            socketIO.emit('land', {'app': 'haobtcnotify', 'events':[self.event]});

        with SocketIO(config.WEBSOCKET_HOST, port=config.WEBSOCKET_PORT) as socketIO:

            socketIO.on('connect', on_connect)
            socketIO.on('message', on_message)

            socketIO.wait()
    
    def ask_update_depth(self):
        try:
            self.update_depth()
            # self.convert_to_usd()
            self.depth_updated = time.time()
            return True
        except Exception as e:
            logging.error("Can't update market: %s - err:%s" % (self.name, str(e)))
            # log_exception(logging.DEBUG)
            return False
            # traceback.print_exc()

    def get_ticker(self):
        depth = self.get_depth()
        if not depth:
            return None

        res = {'ask': {'price': 0, 'amount': 0}, 'bid': {'price': 0, 'amount': 0}}

        if len(depth['asks']) > 0:
            res['ask'] = depth['asks'][0]
        if len(depth["bids"]) > 0:
            res['bid'] = depth['bids'][0] 
        return res

    def sort_and_format(self, l, reverse=False):
        l.sort(key=lambda x: Decimal(str(x[0])), reverse=reverse)
        r = []
        for i in l:
            r.append({'price': Decimal(str(i[0])), 'amount': Decimal(str(i[1]))})
        return r

    def format_depth(self, depth):
        bids = self.sort_and_format(depth['bids'], True)
        asks = self.sort_and_format(depth['asks'], False)
        return {'asks': asks, 'bids': bids}

    ## Abstract methods
    def update_depth(self):
        pass

    def get_kline(self, type, size=None, since=None):
        pass

    def buy(self, price, amount):
        pass

    def sell(self, price, amount):
        pass

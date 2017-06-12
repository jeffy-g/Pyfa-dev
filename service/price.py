# =============================================================================
# Copyright (C) 2010 Diego Duclos
#
# This file is part of pyfa.
#
# pyfa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyfa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyfa.  If not, see <http://www.gnu.org/licenses/>.
# =============================================================================


import time
import threading
import queue
from xml.dom import minidom

from logbook import Logger
import wx

from eos import db
from service.network import Network, TimeoutError
from service.fit import Fit
from service.market import Market

pyfalog = Logger(__name__)


VALIDITY = 24 * 60 * 60  # Price validity period, 24 hours
REREQUEST = 4 * 60 * 60  # Re-request delay for failed fetches, 4 hours
TIMEOUT = 15 * 60  # Network timeout delay for connection issues, 15 minutes


class Price(object):
    instance = None

    systemsList = {
        "Jita": 30000142,
        "Amarr": 30002187,
        "Dodixie": 30002659,
        "Rens": 30002510,
        "Hek": 30002053
    }

    def __init__(self):
        # Start price fetcher
        self.priceWorkerThread = PriceWorkerThread()
        self.priceWorkerThread.daemon = True
        self.priceWorkerThread.start()

    @classmethod
    def getInstance(cls):
        if cls.instance is None:
            cls.instance = Price()
        return cls.instance

    @classmethod
    def fetchPrices(cls, prices):
        """Fetch all prices passed to this method"""

        # Dictionary for our price objects
        priceMap = {}
        # Check all provided price objects, and add invalid ones to dictionary
        for price in prices:
            if not price.isValid:
                priceMap[price.typeID] = price

        if len(priceMap) == 0:
            return

        # Set of items which are still to be requested from this service
        toRequest = set()

        # Compose list of items we're going to request
        for typeID in priceMap:
            # Get item object
            item = db.getItem(typeID)
            # We're not going to request items only with market group, as eve-central
            # doesn't provide any data for items not on the market
            if item is not None and item.marketGroupID:
                toRequest.add(typeID)

        # Do not waste our time if all items are not on the market
        if len(toRequest) == 0:
            return

        # This will store POST data for eve-central
        data = []

        sFit = Fit.getInstance()
        # Base request URL
        baseurl = "https://eve-central.com/api/marketstat"
        data.append(("usesystem", cls.systemsList[sFit.serviceFittingOptions["priceSystem"]]))  # Use Jita for market

        for typeID in toRequest:  # Add all typeID arguments
            data.append(("typeid", typeID))

        # Attempt to send request and process it
        try:
            network = Network.getInstance()
            data = network.request(baseurl, network.PRICES, data)
            xml = minidom.parse(data)
            types = xml.getElementsByTagName("marketstat").item(0).getElementsByTagName("type")
            # Cycle through all types we've got from request
            for type_ in types:
                # Get data out of each typeID details tree
                typeID = int(type_.getAttribute("id"))
                sell = type_.getElementsByTagName("sell").item(0)
                # If price data wasn't there, set price to zero
                try:
                    percprice = float(sell.getElementsByTagName("percentile").item(0).firstChild.data)
                except (TypeError, ValueError):
                    pyfalog.warning("Failed to get price for: {0}", type_)
                    percprice = 0

                # Fill price data
                priceobj = priceMap[typeID]
                priceobj.price = percprice
                priceobj.time = time.time() + VALIDITY
                priceobj.failed = None

                # delete price from working dict
                del priceMap[typeID]

        # If getting or processing data returned any errors
        except TimeoutError:
            # Timeout error deserves special treatment
            pyfalog.warning("Price fetch timout")
            for typeID in list(priceMap.keys()):
                priceobj = priceMap[typeID]
                priceobj.time = time.time() + TIMEOUT
                priceobj.failed = True

                del priceMap[typeID]
        except:
            # all other errors will pass and continue onward to the REREQUEST delay
            pyfalog.warning("Caught exception in fetchPrices")
            pass

        # if we get to this point, then we've got an error. Set to REREQUEST delay
        for typeID in list(priceMap.keys()):
            priceobj = priceMap[typeID]
            priceobj.time = time.time() + REREQUEST
            priceobj.failed = True

    @classmethod
    def fitItemsList(cls, fit):
        # Compose a list of all the data we need & request it
        fit_items = [fit.ship.item]

        for mod in fit.modules:
            if not mod.isEmpty:
                fit_items.append(mod.item)

        for drone in fit.drones:
            fit_items.append(drone.item)

        for fighter in fit.fighters:
            fit_items.append(fighter.item)

        for cargo in fit.cargo:
            fit_items.append(cargo.item)

        for boosters in fit.boosters:
            fit_items.append(boosters.item)

        for implants in fit.implants:
            fit_items.append(implants.item)

        return list(set(fit_items))

    def getPriceNow(self, objitem):
        """Get price for provided typeID"""
        sMkt = Market.getInstance()
        item = sMkt.getItem(objitem)

        return item.price.price

    def getPrices(self, objitems, callback, waitforthread=False):
        """Get prices for multiple typeIDs"""
        requests = []
        for objitem in objitems:
            sMkt = Market.getInstance()
            item = sMkt.getItem(objitem)
            requests.append(item.price)

        def cb():
            try:
                callback(requests)
            except Exception as e:
                pyfalog.critical("Callback failed.")
                pyfalog.critical(e)

            db.commit()

        if waitforthread:
            self.priceWorkerThread.setToWait(requests, cb)
        else:
            self.priceWorkerThread.trigger(requests, cb)

    def clearPriceCache(self):
        pyfalog.debug("Clearing Prices")
        db.clearPrices()


class PriceWorkerThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = "PriceWorker"
        self.queue = queue.Queue()
        self.wait = {}
        pyfalog.debug("Initialize PriceWorkerThread.")

    def run(self):
        queue = self.queue
        while True:
            # Grab our data
            callback, requests = queue.get()

            # Grab prices, this is the time-consuming part
            if len(requests) > 0:
                Price.fetchPrices(requests)

            wx.CallAfter(callback)
            queue.task_done()

            # After we fetch prices, go through the list of waiting items and call their callbacks
            for price in requests:
                callbacks = self.wait.pop(price.typeID, None)
                if callbacks:
                    for callback in callbacks:
                        wx.CallAfter(callback)

    def trigger(self, prices, callbacks):
        self.queue.put((callbacks, prices))

    def setToWait(self, itemID, callback):
        if itemID not in self.wait:
            self.wait[itemID] = []
        self.wait[itemID].append(callback)

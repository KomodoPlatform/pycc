
from pycc import *

class Faucet(PyccSimple):
    @cc_method("")
    def drip(self, tx):
        # We don't care about the other vins, we only care about the vouts
        for vout in tx['outputs']:


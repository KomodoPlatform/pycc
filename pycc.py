
import binascii
from pycoin.coins.bitcoin.Tx import Tx
import io

def parse_tx(txBin):
    buf = io.BytesIO(txBin)
    return Tx.parse(buf, allow_segwit=False)

def parse_tx_hex(hx):
    txBin = binascii.unhexlify(hx)
    return parse_tx(txBin)




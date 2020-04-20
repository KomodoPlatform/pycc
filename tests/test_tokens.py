
from pycc.examples import tokens
from pycc import *
from pycctx import *

class MockChain:
    def get_tx_confirmed(self, txid):
        for tx in [create_tx]:
            if tx.hash == txid:
                return tx
        raise IndexError("Can't find tx with id: %s" % txid)


app = CCApp(tokens.schema, b'_', MockChain())

# keypair = {
#     "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
#     "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
#     "pubkey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
# }
# 
# wifs = (keypair['wif'],)
# 
# # Create a dummy tx for input
# dummy_tx = Tx(
#     inputs = (),
#     outputs = (TxOut(2000, ScriptPubKey.from_address(keypair['addr'])),)
# )
# 
# create_tx = app.create_tx("tokens.create", {
#     "inputs": [
#         { "previous_output": (dummy_tx.hash, 0), "script": { "address": keypair['addr'] } }
#     ],
#     "outputs": [
#         [ { "script": { "tokenoshi": 2000 } }
#         , { "script": { "tokenoshi": 2000 } } ]
#     ]
# })
# create_tx.sign(wifs, [dummy_tx])

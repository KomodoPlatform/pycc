
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

keypair = {
    "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
    "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
    "pubkey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
}

wifs = (keypair['wif'],)

# Create a dummy tx for input
dummy_tx = Tx(
    outputs = (TxOut(2000, ScriptPubKey.from_address(keypair['addr'])),)
)

create_tx = app.create_tx({
    "name": "token.create",
    "inputs": [
        { "previous_output": (dummy_tx.hash, 0), "script": { "address": keypair['addr'] } }
    ],
    "outputs": [
        [ { "tokenoshi": 2000, "script": { "pubkey": keypair['pubkey'] } }
        , { "tokenoshi": 2000, "script": { "pubkey": keypair['pubkey'] } }
        ],
        [ { "script": { "address": keypair['addr'] }, "amount": 1000 } ]
    ]
})
create_tx.sign(wifs, [dummy_tx])


transfer_tx = app.create_tx({
    "name": "token.transfer",
    "inputs": [
        [ { "previous_output": (create_tx.hash, 0), "script": { "pubkey": keypair['pubkey'] } }
        , { "previous_output": (create_tx.hash, 1), "script": { "pubkey": keypair['pubkey'] } }
        ],
        { "previous_output": (create_tx.hash, 2), "script": { "address": keypair['addr'] } }
    ],
    "outputs": [
        [ { "tokenoshi": 4000, "script": { "pubkey": keypair['pubkey'] } } ],
        [ { "script": { "address": keypair['addr'] }, "amount": 1000 } ]
    ]
})

transfer_tx.sign(wifs, [create_tx])

def test_validate_transfer():

    spec = app.validate_tx(transfer_tx)
    del spec['inputs'][1]['script']['signature']

    assert spec == {
        'txid': transfer_tx.hash,
        "name": "token.transfer",
        "inputs": [
            [ { "previous_output": (create_tx.hash, 0), "script": { "pubkey": keypair['pubkey'] } }
            , { "previous_output": (create_tx.hash, 1), "script": { "pubkey": keypair['pubkey'] } }
            ],
            { "previous_output": (create_tx.hash, 2), "script": {
                "address": keypair['addr'],
                "pubkey": keypair['pubkey'],
               }
            }
        ],
        "outputs": [
            [ { "tokenoshi": 4000, "amount": None, "script": { "pubkey": keypair['pubkey'] } } ],
            [ { "script": { "address": keypair['addr'] }, "amount": 1000 } ]
        ]
    }
    
    # Check it can re-create itself
    ttx = app.create_tx(spec)
    ttx.sign(wifs, [create_tx])
    assert ttx.hash == transfer_tx.hash

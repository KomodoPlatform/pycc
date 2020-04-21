
from pycc import CCApp, Tx, TxOut, ScriptPubKey

from pycc.examples import tokens


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

create_spec = {
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
}

create_tx = app.create_tx(create_spec)
create_tx.sign(wifs, [dummy_tx])


transfer_spec = {
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
}

transfer_tx = app.create_tx(transfer_spec)
transfer_tx.sign(wifs, [create_tx])


def _validate(tx, given_spec):
    spec = app.validate_tx(tx)
    # Have to make some modifications, result is superset of input spec
    assert spec.pop('txid') == tx.hash
    assert spec['inputs'][-1]['script'].pop('pubkey') == keypair['pubkey']
    del spec['inputs'][-1]['script']['signature']
    for o in spec['outputs'][0]:
        assert o.pop('amount') is None
    assert spec == given_spec

def test_create():
    _validate(create_tx, create_spec)

def test_transfer():
    _validate(transfer_tx, transfer_spec)

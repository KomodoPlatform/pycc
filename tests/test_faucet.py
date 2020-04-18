
from pycc.examples import faucet
from pycc import *
from pycctx import *

app = CCApp(faucet.schema, b'_')

keypair = {
    "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
    "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
    "pubkey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
}

# Create a dummy tx for input
dummy_tx = Tx(
    inputs = (),
    outputs = (TxOut(1000, ScriptPubKey.from_address(keypair['addr'])),)
)


create_tx = app.create_tx("faucet.create", {}, {
    "inputs": [
        { "previous_output": (dummy_tx.hash, 0), "script": {"address": keypair['addr']} }
    ],
    "outputs": [
        {"script": {"pubkey": keypair['pubkey']}, "amount": 1000 }
    ]
})

create_tx.sign([keypair['wif']], [dummy_tx])


def test_validate_create():
    o = app.cc_eval({}, create_tx.encode_bin())

    assert o == {
        'txid': '0304c852823c7ac1f7212bcdb5d6221bcb302c2d798237f5f516235c037f209a',
        'inputs': [
            {
                'previous_output': (dummy_tx.hash, 0),
                'script': {
                    'address': keypair['addr'],
                    'pubkey': keypair['pubkey'],
                    'signature': '3044022071a042a552efc354f71a8968fc02d538d5a51a7c86b70089c5986202368504a002206d46c474e47f97cefed337fde1ca55f96f91dc2a7edd72c88d97a52b3345f7e801'
                }
            },
        ],
        'outputs': [
            { 'amount': 1000, 'script': { "pubkey": keypair['pubkey'] } }
        ],
    }
    
    # Check it can re-create itself
    create_tx_2 = app.create_tx("faucet.create", {}, o)
    create_tx_2.sign([keypair['wif']], [dummy_tx])
    assert create_tx_2.hash == create_tx.hash




# drip_tx = Tx(
#     inputs = [
#         TxIn((create_tx.hash, 0), ScriptSig.from_condition(cond))
#     ],
#     outputs = [
#         TxOut(999000, ScriptPubKey.from_condition(cond)),
#         TxOut(1000, ScriptPubKey.from_address(keypair['addr'])),
#         TxOut.op_return(b"faucet.drip")
#     ]
# )
# 
# drip_tx.sign([keypair['wif']], [create_tx])


# def test_validate_drip():
#     o = app.cc_eval({}, drip_tx.encode_bin(), 0, b'_')
#     assert o == {
#         "inputs": [{"idx": 0, "txid": dummy_tx.hash}],
#         "outputs": [{"amount": 999000}, {"amount": 1000, "address": keypair['addr']}],
#         "txid": drip_tx.hash
#     }


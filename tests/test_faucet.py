
from pycc.examples import faucet
from pycc import *
from pycctx import *

app = CCApp(faucet.schema)

keypair = {
    "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
    "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
    "pubkey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
}

txid_1 = "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"

cond = cc_threshold(2, [
    cc_eval(b'_'),
    cc_secp256k1(keypair['pubkey'])
    ])

create_tx = Tx(
    inputs = [
        TxIn((txid_1, 0), ScriptSig.from_address(keypair['addr']), input_amount=1)
    ],
    outputs = [
        TxOut(1000000, ScriptPubKey.from_condition(cond)),
        TxOut.op_return(encode_params(["faucet.create", hex_decode(keypair['pubkey'])]))
    ]
)
create_tx.sign([keypair['wif']])


def test_validate_create():
    o = app.cc_eval({}, create_tx.encode_bin(), 0, b"_")

    assert o == {
        'txid': '83358a4d6068dbf2404679dfa2f43cf9c7bc64cd6494e8ba47810fd7f97c6476',
        'inputs': [
            {
                'previous_output': ('d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43', 0),
                'address': {
                    'address': 'RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs',
                    'pubkey': '038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63',
                    'signature': '3045022100e3e3e334f737f12a105daf8f978033aed117398a8c27c8a042f30992e61b32fe0220130d887e40f8ac2b2e472eff881960199709b879f31bc0c13ec8089b6f373d0301'
                }
            },
        ],
        'outputs': [
            {
                'amount': 0,
                'condition': {
                    'type': 'threshold-sha-256',
                    'threshold': 2,
                    'subconditions': [{'code': '5f', 'type': 'eval-sha-256'}, {'pubkey': '038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63', 'type': 'secp256k1-sha-256'}],
                }
            }
        ],
    }


drip_tx = Tx(
    inputs = [
        TxIn((create_tx.hash, 0), ScriptSig.from_condition(cond))
    ],
    outputs = [
        TxOut(999000, ScriptPubKey.from_condition(cond)),
        TxOut(1000, ScriptPubKey.from_address(keypair['addr'])),
        TxOut.op_return(b"faucet.drip")
    ]
)

drip_tx.sign([keypair['wif']], [create_tx])


# def test_validate_drip():
#     o = app.cc_eval({}, drip_tx.encode_bin(), 0, b'_')
#     assert o == {
#         "inputs": [{"idx": 0, "txid": txid_1}],
#         "outputs": [{"amount": 999000}, {"amount": 1000, "address": keypair['addr']}],
#         "txid": drip_tx.hash
#     }


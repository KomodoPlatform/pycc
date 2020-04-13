
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
        'txid': '251d47575d69996006d29e2b4f14608795842008992a740dc6c701a3045b62af',
        'inputs': [
            {
                'previous_output': ('d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43', 0),
                'address': {
                    'address': 'RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs',
                    'pubkey': '038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63',
                    'signature': '304402200ff7281dc16a4f9e13c4ec653e86cc59c50235621112338c130b74a5547d41dc02203470c46140047811f3fc143daba8cec42d83271c20b8f1b6b3384606bc36391401'
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


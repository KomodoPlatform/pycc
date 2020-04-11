
import pytest
from pycctx import *
import base64

address0 = "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs"
outpoint0 = ("d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43", 3)

keypair = {
    "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
    "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
    "pubkey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
}


def test_encode_vin():
    vin = TxIn(outpoint0, ScriptSig.from_address(address0))
    assert vin.to_py() == {
        "previous_output": outpoint0,
        "script": {
            "address": {
                "address": address0,
            }
        }
    }

def test_tx_decode():
    tx = Tx.decode('01000000000000000000')
    assert tx.hash == "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"
    assert tx.to_py() == {
        "inputs": [],
        "outputs": []
    }

def test_known_good():
    rawtx = "010000000100b7a74ee48ac1f9a4ba3234b7398302a84e4b618bb463b46a2c23fe5a628700000000007b4c79a276a072a26ba067a565802103682b255c40d0cde8faee381a1a50bbb89980ff24539cb8518e294d3a63cefe128140b65222f7057268e48bb729ab43b7279e4eb22b82f8e6f0e559c05ff68ec4e3ed24f7d1c8095d04c21c9ce926a5bcb0b91da86e3614f46babd074c9776bc7978aa100af038001e4a10001ffffffff03e0e99b1c00000000302ea22c8020e029c511da55523565835887e412e5a0c9b920801b007000df45e545f25028248103120c008203000401cc8096980000000000232103174bf5ead8d6cf74c2e2a3dbb7149455c850243a14684baf41db1c0b19e6cc5dac0000000000000000086a06e44767458b0b00000000"
    tx = Tx.decode(rawtx)
    assert tx.to_py() == {
        'inputs': [
            {'previous_output': ('0087625afe232c6ab463b48b614b4ea8028339b73432baa4f9c18ae44ea7b700',
                                 0),
             'script': b'Ly\xa2v\xa0r\xa2k\xa0g\xa5e\x80!\x03h+%\\@'
                       b'\xd0\xcd\xe8\xfa\xee8\x1a\x1aP\xbb\xb8\x99'
                       b'\x80\xff$S\x9c\xb8Q\x8e)M:c\xce\xfe\x12\x81@\xb6R"'
                       b"\xf7\x05rh\xe4\x8b\xb7)\xabC\xb7'\x9eN\xb2+"
                       b'\x82\xf8\xe6\xf0\xe5Y\xc0_\xf6\x8e\xc4\xe3'
                       b'\xed$\xf7\xd1\xc8\t]\x04\xc2\x1c\x9c\xe9'
                       b'&\xa5\xbc\xb0\xb9\x1d\xa8n6\x14\xf4k\xab\xd0t\xc9'
                       b'wk\xc7\x97\x8a\xa1\x00\xaf\x03\x80\x01\xe4'
                       b'\xa1\x00\x01'
            }
        ],
        'outputs': [
            {'script': b'.\xa2,\x80 \xe0)\xc5\x11\xdaUR5e\x83X'
                       b'\x87\xe4\x12\xe5\xa0\xc9\xb9 \x80\x1b\x00p'
                       b'\x00\xdfE\xe5E\xf2P($\x81\x03\x12'
                       b'\x0c\x00\x82\x03\x00\x04\x01\xcc',
             'amount': 479980000
            },
            {'script': b'!\x03\x17K\xf5\xea\xd8\xd6\xcft\xc2\xe2'
                       b'\xa3\xdb\xb7\x14\x94U\xc8P$:\x14hK\xafA\xdb'
                       b'\x1c\x0b\x19\xe6\xcc]\xac',
             'amount': 10000000
             },
             {'script': b'j\x06\xe4GgE\x8b\x0b',
              'amount': 0
             }
        ]
    }

    input_script = tx.inputs[0].script.to_py()
    assert input_script[0] == 76
    ffill_bin = input_script[2:-1]
    ffill_hex = base64.b16encode(ffill_bin).decode()
    cond = Condition.decode_fulfillment(ffill_hex)

    mtx = Tx(
        inputs = [
            TxIn(tx.inputs[0].previous_output, ScriptSig.from_condition(cond), sequence=0xffffffff),
        ],
        outputs = tx.outputs,
        version = 1
    )
    assert mtx.encode() == rawtx
    

def test_construct():
    # test invalid hash
    with pytest.raises(ValueError):
        TxIn(("876",1), ScriptSig(b"\0a"))

    # test valid hash
    some_hash = "0087625afe232c6ab463b48b614b4ea8028339b73432baa4f9c18ae44ea7b700"
    vin = TxIn((some_hash, 1), ScriptSig(b"\0a"))
    vout = TxOut(1, ScriptPubKey(b""))

    # test full tx
    mtx = Tx()
    mtx.inputs = (vin,)
    mtx.outputs = (vout,)
    assert mtx.to_py() == {
        'inputs': [
            {'previous_output': (some_hash, 1),
             'script': b'\x00a'}
        ],
        'outputs': [{'script': b'', 'amount': 1}]
    }


def test_sign():
    tx = Tx()
    tx.inputs = (TxIn(outpoint0, ScriptSig.from_address(keypair["addr"]), input_amount=0),
            TxIn(outpoint0, ScriptSig.from_condition(cc_secp256k1(keypair["pubkey"])), input_amount=0))

    with pytest.raises(TxSignError):
        tx.sign(["UroCh5e8855Cv31jBvR8zYH3ykuEVK84U8QsELHubSsJRemD35QV"])

    tx.sign([keypair['wif']])
    tx.hash

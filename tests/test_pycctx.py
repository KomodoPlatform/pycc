
import pytest
from pycctx import *


def test_tx_decode():
    tx = Tx.from_hex('01000000000000000000')
    assert tx.txid == "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"
    assert tx.to_py() == {
        "inputs": [],
        "outputs": []
    }

def test_known_good():
    tx = Tx.from_hex("010000000100b7a74ee48ac1f9a4ba3234b7398302a84e4b618bb463b46a2c23fe5a628700000000007b4c79a276a072a26ba067a565802103682b255c40d0cde8faee381a1a50bbb89980ff24539cb8518e294d3a63cefe128140b65222f7057268e48bb729ab43b7279e4eb22b82f8e6f0e559c05ff68ec4e3ed24f7d1c8095d04c21c9ce926a5bcb0b91da86e3614f46babd074c9776bc7978aa100af038001e4a10001ffffffff03e0e99b1c00000000302ea22c8020e029c511da55523565835887e412e5a0c9b920801b007000df45e545f25028248103120c008203000401cc8096980000000000232103174bf5ead8d6cf74c2e2a3dbb7149455c850243a14684baf41db1c0b19e6cc5dac0000000000000000086a06e44767458b0b00000000")
    assert tx.to_py() == {
        'inputs': [
            {'previous_output': ('0087625afe232c6ab463b48b614b4ea8028339b73432baa4f9c18ae44ea7b700',
                                 0),
             'script_sig': b'Ly\xa2v\xa0r\xa2k\xa0g\xa5e\x80!\x03h+%\\@'
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
            {'script_pubkey': b'.\xa2,\x80 \xe0)\xc5\x11\xdaUR5e\x83X'
                               b'\x87\xe4\x12\xe5\xa0\xc9\xb9 \x80\x1b\x00p'
                               b'\x00\xdfE\xe5E\xf2P($\x81\x03\x12'
                               b'\x0c\x00\x82\x03\x00\x04\x01\xcc',
             'value': 479980000
            },
            {'script_pubkey': b'!\x03\x17K\xf5\xea\xd8\xd6\xcft\xc2\xe2'
                               b'\xa3\xdb\xb7\x14\x94U\xc8P$:\x14hK\xafA\xdb'
                               b'\x1c\x0b\x19\xe6\xcc]\xac',
             'value': 10000000
             },
             {'script_pubkey': b'j\x06\xe4GgE\x8b\x0b',
              'value': 0
             }
        ]
    }

def test_construct():
    # test invalid hash
    with pytest.raises(DecodeError):
        TxIn(("876",1), b"\0a")

    # test valid hash
    some_hash = "0087625afe232c6ab463b48b614b4ea8028339b73432baa4f9c18ae44ea7b700"
    vin = TxIn((some_hash,1), b"\0a")
    vout = TxOut(1, b"")

    # test full tx
    mtx = MutableTx()
    mtx.inputs = (vin,)
    mtx.outputs = (vout,)
    assert mtx.to_py() == {
        'inputs': [
            {'previous_output': (some_hash, 1),
             'script_sig': b'\x00a'}
        ],
        'outputs': [{'script_pubkey': b'', 'value': 1}]
    }

    # test freeze
    tx = mtx.freeze()
    assert mtx.to_py() == tx.to_py()


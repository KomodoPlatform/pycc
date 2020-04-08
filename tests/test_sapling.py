#import pytest
from pycctx import *


# createrawtransaction "[{\"txid\":\"726dffd87d11f8e1b5d4012966a4702e30365a174c4196da5b0de9d6cea5a8ff\",\"vout\":0}]" "{}"
def test_sapling_vin_txid():
    known_hex = "0400008085202f8901ffa8a5ced6e90d5bda96414c175a36302e70a4662901d4b5e1f8117dd8ff6d720000000000ffffffff0000000000d40000000000000000000000000000"
    known_txid = "bee4dee48414a42b748d74589c7f7032a9cccfd33d8962fb1d770834a29503e9"
    
    tx = Tx.decode(known_hex)
    assert tx.hash == known_txid

def test_sapling_vin_encode():
    known_hex = "0400008085202f8901ffa8a5ced6e90d5bda96414c175a36302e70a4662901d4b5e1f8117dd8ff6d720000000000ffffffff0000000000d40000000000000000000000000000"
    known_txid = "bee4dee48414a42b748d74589c7f7032a9cccfd33d8962fb1d770834a29503e9"
    
    tx = Tx.decode(known_hex)
    assert tx.hash == known_txid


# createrawtransaction "[]" "{\"RMzjEbvAJNRFVTJ6Uai19FVC4Uzo1UeZ17\":9.9999}"
def test_sapling_vout_txid():
    known_hex = "0400008085202f890001f0a29a3b000000001976a9148b7c92762bf98001d4d8e74eef212d59e4ce9a2b88ac00000000d40000000000000000000000000000"
    known_txid = "83cdfe5f3350de4095c699b59669a48e3383e02d368c1bad31ee2dc408e20580"
    
    tx = Tx.decode(known_hex)
    assert tx.hash == known_txid

def test_sapling_vout_encode():
    known_hex = "0400008085202f890001f0a29a3b000000001976a9148b7c92762bf98001d4d8e74eef212d59e4ce9a2b88ac00000000d40000000000000000000000000000"
    known_txid = "83cdfe5f3350de4095c699b59669a48e3383e02d368c1bad31ee2dc408e20580"
    
    tx = Tx.decode(known_hex)
    assert tx.hash == known_txid
    
# FIXME currently failing because rust app seems unaware of VersionGroupid
def test_sapling_vout_create():
    known_hex = "0400008085202f890001f0a29a3b000000001976a9148b7c92762bf98001d4d8e74eef212d59e4ce9a2b88ac00000000d40000000000000000000000000000"
    
    known_tx = Tx.decode(known_hex)
    mtx = Tx()
    
    script = ScriptPubKey(b"")
    script = script.from_address("RMzjEbvAJNRFVTJ6Uai19FVC4Uzo1UeZ17")
    
    vout = TxOut(999990000, script)
    mtx.outputs = (vout,)
    mtx.version = 4
    assert mtx.encode() == known_hex
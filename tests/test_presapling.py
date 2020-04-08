#import pytest
from pycctx import *


# createrawtransaction "[{\"txid\":\"a05095c92dcadb6d9c600bb96bb276fbf98ea49cad0af1349f839876ad119976\",\"vout\":0}]" "{}"

def test_presapling_vin_txid():
    known_hex = "0100000001769911ad7698839f34f10aad9ca48ef9fb76b26bb90b609c6ddbca2dc99550a00000000000ffffffff0000000000"
    known_txid = "6faf013a3293eb17b7bf1a1fe010cfb189cd2ae8fae9e3307f14ae5248817358"
    
    tx = Tx.decode(known_hex)
    assert tx.hash == known_txid

# test single vin decode -> encode is equal
def test_presapling_vin_encode():
    known_hex = "0100000001769911ad7698839f34f10aad9ca48ef9fb76b26bb90b609c6ddbca2dc99550a00000000000ffffffff0000000000"
    known_txid = "6faf013a3293eb17b7bf1a1fe010cfb189cd2ae8fae9e3307f14ae5248817358"
    
    tx = Tx.decode(known_hex)
    assert tx.encode() == known_hex

# create a vin compare against known good vin; can fail if Tx.decode() breaks
def test_presapling_vin_create():
    known_hex = "0100000001769911ad7698839f34f10aad9ca48ef9fb76b26bb90b609c6ddbca2dc99550a00000000000ffffffff0000000000"
    known_vin_txid = "a05095c92dcadb6d9c600bb96bb276fbf98ea49cad0af1349f839876ad119976"

    tx = Tx.decode(known_hex)
    vin = TxIn((known_vin_txid, 0), ScriptSig(b""))
    assert tx.inputs[0].to_py() == vin.to_py()


# createrawtransaction "[]" "{\"RMzjEbvAJNRFVTJ6Uai19FVC4Uzo1UeZ17\":9.9999}"
def test_presapling_vout_txid():
    known_hex = "010000000001f0a29a3b000000001976a9148b7c92762bf98001d4d8e74eef212d59e4ce9a2b88ac00000000"
    known_txid = "caad819da47aaca0640df6b33b632032fcd46436abf0634a76b68084f91316ec"
    
    tx = Tx.decode(known_hex)
    assert tx.hash == known_txid

def test_presapling_vout_encode():
    known_hex = "010000000001f0a29a3b000000001976a9148b7c92762bf98001d4d8e74eef212d59e4ce9a2b88ac00000000"
    known_txid = "caad819da47aaca0640df6b33b632032fcd46436abf0634a76b68084f91316ec"
    
    tx = Tx.decode(known_hex)
    assert tx.encode() == known_hex


def test_presapling_vout_create():
    known_hex = "010000000001f0a29a3b000000001976a9148b7c92762bf98001d4d8e74eef212d59e4ce9a2b88ac00000000"
    
    known_tx = Tx.decode(known_hex)
    mtx = Tx()
    
    script = ScriptPubKey(b"")
    script = script.from_address("RMzjEbvAJNRFVTJ6Uai19FVC4Uzo1UeZ17")
    
    vout = TxOut(999990000, script)
    mtx.outputs = (vout,)
    mtx.version = 1
    assert mtx.encode() == known_hex
    
    
    

    
    
    
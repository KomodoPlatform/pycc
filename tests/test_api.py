
import binascii
from pycc import *


def test_parse_minimal():
    # hoek encodeTx '{"inputs":[],"outputs":[]}'
    tx = parse_tx_hex("01000000000000000000")

    assert tx.txs_in == []
    assert tx.id() == "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"

def test_parse_cc_tx():
    # hoek encodeTx '{"inputs":[{"txid":"d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43","idx":0,"script":{"fulfillment":{"type":"eval-sha-256","code":"0123"}}}],"outputs":[]}'

    tx = parse_tx_hex("010000000143ec7a579f5561a42a7e9637ad4156672735a658be2752181801f723ba3316d2000000000807af058003d35db7000000000000000000")

    assert tx.id() == "f154b783b588368f8356d0cd8ea11c50e9fae05658a376340070cb98a573ea3d"
    assert len(tx.txs_in) == 1
    assert repr(tx.txs_in[0].previous_hash) == "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"
    assert tx.txs_in[0].script == b'\x07\xaf\x05\x80\x03\xd3]\xb7'
    assert tx.txs_in[0].previous_index == 0


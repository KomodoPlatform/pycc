
from pycctx import *


def test_tx_decode():
    assert tx_from_hex('01000000000000000000').txid == "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"


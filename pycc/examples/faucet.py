
from pycc import *


schema = {
    "faucet": {
        "create": {
            "inputs": [
                P2PKH()
            ],
            "outputs": [
                CCEval("faucet.transfer", 0),
            ]
        },
        "transfer": {
            "inputs": [
                # OneOf([Ref("faucet.create", 0), Ref("faucet.transfer", 0)])
                Ref("faucet.create", 0)
            ],
            "outputs": [
                CCEval("faucet.transfer", 0),
                P2PKH()
            ]
        }
    }
}

app = CCApp(schema)

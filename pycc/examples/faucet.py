
from pycc import *


def validate_faucet_drip(ctx, tx_data):
    # Is there anything to validate?
    pass


schema = {
    "faucet": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Output(CCEval("faucet.drip", 0)),
            ],
        },
        "drip": {
            "inputs": [
                Input(Ref("faucet.create", 0))
            ],
            "outputs": [
                Output(CCEval("faucet.drip", 0)), # , InputAmount(0).subtract(0.1)),
                Output(P2PKH())
            ],
            "validate": validate_faucet_drip
        },
    }
}


# asset_schema = {
#     "asset": {
#         "create": {
#             "inputs": [
#                 Input(P2PKH())
#             ],
#             "outputs": [
#                 Output(CCEval("asset.transfer", 0))
#             ]
#         },
#         "transfer": {
#             "inputs": [
#                 Inputs(CCEval("asset.transfer", 0), min=1, max=5),
#                 Input(P2PKH())
#             ],
#             "outputs": [
#                 Outputs(CCEval("asset.transfer", 0)),
#                 Output(P2PKH())
#             ],
#             "validate": validate_asset_transfer
#         }
#     }
# }


from pycc import *
from pycctx import *
import json
import traceback
import pycc.active_cc.faucet as faucet
import pycc.active_cc.tokens as tokens


# this is where we can define which CCs are active on a given chain, if they are not defined here, validation will fail 100% of the time
# maybe a more elegant way of doing this, but each chain could have their own version of this "active.py" 
cc_info = {"faucet": faucet.info,
           "tokens": tokens.info}


def help_info(specific=None):
    all_help = {}
    for i in cc_info:
        if i == specific:
            return(json.dumps(cc_info[i]['help']))
        all_help[i] = cc_info[i]['help']
    return(json.dumps(all_help))


def find_schema(eval_code):
    for i in cc_info:
        if cc_info[i]['eval'] == eval_code:
            return(cc_info[i]['schema'])


def cc_eval(chain, tx_bin, nIn, eval_code):
    return CCApp(find_schema(eval_code), eval_code, chain).cc_eval(tx_bin)


def cc_cli(chain, code):
    try:
        code = json.loads(code)
        try:
            app = CCApp(cc_info[code[0]]['schema'], cc_info[code[0]]['eval'], chain)
            try:
                return(cc_info[code[0]]['functions'][code[1]](app, *code[2:]))
            except (KeyError, IndexError):
                return(help_info(code[0])) # return module-specific help_info because method is in cc_info
        except (KeyError, IndexError):
            return help_info() # return all help_infos because method was not found in cc_info
    # IntendExcept can be raised to send error msg back to komodod
    except IntendExcept as e:
        return rpc_error(e)
    except Exception as e:
        return rpc_error(traceback.format_exc())
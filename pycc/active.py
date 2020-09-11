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

# FIXME really need to clean this mess up, maybe it's fine as devs/users should never have to touch it 
def cc_cli(chain, code):
    try:
        code = json.loads(code)
        if code[-1] == 'MakeState': 
            try:
                eval_code = code[-3]
                module_info = find_module_info(eval_code)
                prevblock = json.loads(code[-2])
                events = ParseOpRets(code[:-3], eval_code)
                if 'special_events' in module_info:
                    events = module_info['special_events'](prevblock, events)
                newstate = MakeState(prevblock, events, module_info)
                print({module_info['name']: newstate})
                return(json.dumps({module_info['name']: newstate}))
            except Exception as e: 
                print(traceback.format_exc()) # should leave this print active as there is no indication from within komodod as to why it failed
                return(False) # this will ensure that block creation fails gracefully if something goes wrong in MakeState
        if code[0] in cc_info: # FIXME make a case for `pycli <module_name>`
            app = CCApp(cc_info[code[0]]['schema'], cc_info[code[0]]['eval'], chain)
            if len(code) > 1 and code[1] in cc_info[code[0]]['functions']:
                return(cc_info[code[0]]['functions'][code[1]](app, *code[2:]))
            else:
                return(help_info(code[0]))
        else:
            return help_info()
    # IntendExcept can be raised to send error msg back to komodod
    except IntendExcept as e:
        return rpc_error(e)
    except Exception as e:
        return rpc_error(traceback.format_exc())
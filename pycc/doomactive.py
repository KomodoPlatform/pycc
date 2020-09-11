from pycc import *
from pycctx import *
import json
import traceback
import pycc.active_cc.doom as doom

import pdb
import dsm
import ast

# this is where we can define which CCs are active on a given chain, if they are not defined here, validation will fail 100% of the time
# maybe a more elegant way of doing this, but each chain could have their own version of this "active.py" 
cc_info = {"doom": doom.info}

###### FIXME move these helpers elsewhere or at least clean them up into classes
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


# take full hex txes and extract state change field
def ParseOpRets(txes, eval_code):
    events = []
    module_name = find_module_info(eval_code)['name']
    for tx_hex in txes:
        tx = Tx.decode(tx_hex)
        opret = tx.outputs[-1]
        if module_name in ast.literal_eval(opret.script.get_opret_data().decode())[2]: # FIXME CLEAN UP
            events.append(ast.literal_eval(opret.script.get_opret_data().decode())[2][module_name])

    return(events)

# extract a state from pycctx tx object by module_name
def find_miner_states(miner_tx):
    states = {}
    for opret in miner_tx.outputs:
        state_dict = ast.literal_eval(opret.script.get_opret_data()[4:].decode())
        states = {**states, **state_dict}
    return(states)

# extract a state from pycctx tx object by module_name
def find_miner_state(miner_tx, module_name):
    for opret in miner_tx.outputs:
        state_dict = ast.literal_eval(opret.script.get_opret_data()[4:].decode())
        if module_name in state_dict:
            return(state_dict[module_name])

# find cc_info via ascii eval_code, eg, "6565"
def find_module_info(eval_code):
    for i in cc_info:
        if binascii.hexlify(cc_info[i]['eval']).decode() == eval_code:
            return(cc_info[i])
########



def cc_eval(chain, tx_bin, nIn, eval_code):
    if eval_code == b'\xe2': # FIXME a very special case, be extra careful, can mint coins if misconfigured
        return(None)
    return CCApp(find_schema(eval_code), eval_code, chain).cc_eval(tx_bin)
    # FIXME could except AssertionError here if we want prettier stdout 


# FIXME move this to individual modules, allow them to define the state machine however they like 
# dsm lib not required, can arbitrarily define how this machine works
def MakeState(prevblockJSON, events, module_info):
    print("MY MAKE STATE EVENTS", events)
    minerstate_tx = Tx.decode(prevblockJSON['minerstate_tx'])
    prevstate = find_miner_state(minerstate_tx, module_info['name'])
    # FIXME need to implement a special case for initializing a state when a new pycc module with FSM is introduced 
    #try:
    #     prevstate = ParseOpRets([prevopret], True)
    #except Exception as e:
    #    prevstate = {"state":'on'} # this is for the first block where this pycc module is introduced, need to be sure this cannot happen otherwise
    fsm = dsm.StateMachine(initial=prevstate,
                       transitions=dsm.Transitions(module_info['FSM']))

    if events:
        fsm.process_many(events)
    return(fsm.state)



# this allows for validating a block as a whole, is the ground-work for a global statemachine
# we should be able to assume that any events that were able to enter the mempool are valid events, if not, bugs in CC's schema 

# return None to pass validation
# raise an exception or return a string and message will go back to komodod stdout

# TODO evalulate what other data would be useful here, add relevant fields to pycc.cpp:tempblockToJSON
# maybe generalize this per module
def cc_block_eval(blockJSON, prevblockJSON):
    block = json.loads(blockJSON)
    prevblock = json.loads(prevblockJSON)
    states = {}
    miner_tx = Tx.decode(block['minerstate_tx'])


    prevminer_tx = Tx.decode(block['minerstate_tx'])
    prevstates = find_miner_states(prevminer_tx)
    for module in prevstates:
        block['cc_spends'][binascii.hexlify(cc_info[module]['eval']).decode()] = {}

    for eval_code in block['cc_spends']:
        module_info = find_module_info(eval_code)
        events = ParseOpRets(block['cc_spends'][eval_code], eval_code)
        if 'special_events' in module_info:
            events = module_info['special_events'](prevblock, events)
        newstate = MakeState(prevblock, events, module_info)
        states[module_info['name']] = newstate


    for module_name in states:
        check_state = find_miner_state(miner_tx, module_name)
        if check_state != states[module_name]:
            return( "PyCC cc_block_eval failed mystate:" + 
                    states[module_name] + " != minerstate:" +
                    check_state + " for module:" + module_name)


# FIXME really need to clean this mess up, maybe it's fine as devs/users should never have to touch it 
def cc_cli(chain, code):
    #print("COOOODEEEE", code)
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
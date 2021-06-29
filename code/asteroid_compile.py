###########################################################################################
# Asteroid compiler
#
# (c) University of Rhode Island
###########################################################################################

import sys
from asteroid_globals import *
from  asteroid_support import *
from pathlib import Path
from asteroid_frontend import Parser
from asteroid_state import state

# the prologue file is expected to be in the 'modules' folder
prologue_name = 'prologue.ast'

# TODO: adjust the defaults
def compile(input_stream,
            input_name = "<input>",
            tree_dump=False,
            prologue=True):
    try:
        # initialize state
        state.initialize()

        #lhh
        #print("path[0]: {}".format(sys.path[0]))
        #print("path[1]: {}".format(sys.path[1]))

        # read in prologue
        if prologue:
            # load the prologue file
            prologue_file_base = '/modules/' + prologue_name

            if Path(sys.path[0] + prologue_file_base).is_file():
                prologue_file = sys.path[0] + prologue_file_base
                #lhh
                #print("path[0]:"+prologue_file)
            elif Path(sys.path[1] + prologue_file_base).is_file():
                prologue_file = sys.path[1] + prologue_file_base
                #lhh
                #print("path[1]:"+prologue_file)
            else:
                raise ValueError("Asteroid prologue '{}' not found"
                                .format(prologue_file_base))

            with open(prologue_file) as f:
                state.modules.append(prologue_name)
                data = f.read()
                pparser = Parser(prologue_name)
                (LIST, pstmts) = pparser.parse(data)

        # build the AST
        parser = Parser(input_name)
        (LIST, istmts) = parser.parse(input_stream)
        if prologue:
            state.AST = ('list', pstmts + istmts)
        else:
            state.AST = ('list', istmts)

        # walk the AST
        if tree_dump:
            dump_AST(state.AST)

        return state.AST


    except Exception as e:
        module, lineno = state.lineinfo
        print("Error: {}: {}: {}".format(module, lineno, e))
        sys.exit(1)

    except  KeyboardInterrupt as e:
        print("Error: keyboard interrupt")
        sys.exit(1)

    except  BaseException as e:
        print("Error: {}".format(e))
        sys.exit(1)

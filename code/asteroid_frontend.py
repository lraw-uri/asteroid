###########################################################################################
# front end for Asteroid
#
# (c) Lutz Hamel, University of Rhode Island
###########################################################################################

import sys
from asteroid_globals import asteroid_file_suffix
from pathlib import Path, PurePath
from asteroid_lex import Lexer
from asteroid_state import state

###########################################################################################
def dbg_print(string):
    #print(string)
    pass

###########################################################################################
# LL(1) lookahead sets

ops = {
    'TIMES',
    'NOT',
    'MINUS',
    }

primary_lookahead = {
    'ESCAPE',
    'EVAL',
    'LAMBDA',
    'INTEGER',
    'REAL',
    'STRING',
    'TRUE',
    'FALSE',
    'NONE',
    'ID',
    'LBRACKET',
    'LPAREN',
    'TYPEMATCH',
    } | ops

exp_lookahead = {
    'QUOTE',
    'LCONSTRAINT',} | primary_lookahead

exp_lookahead_no_ops = exp_lookahead - ops - {'QUOTE'}

primary_lookahead_no_ops = exp_lookahead_no_ops

stmt_lookahead = {
    'DOT',
    'ASSERT',
    'BREAK',
    'FOR',
    'FUNCTION',
    'GLOBAL',
    'IF',
    'LET',
    'LOAD',
    'LOOP',
    'NONLOCAL',
    'REPEAT',
    'RETURN',
    'STRUCTURE',
    'THROW',
    'TRY',
    'WHILE',
    'WITH',
    } | primary_lookahead

###########################################################################################
class Parser:

    def __init__(self, filename="<input>"):
        self.lexer = Lexer()
        state.lineinfo = (filename,1)

    ###########################################################################################
    def parse(self, input):
        self.lexer.input(input)
        return self.prog()

    ###########################################################################################
    # prog:
    #   stmt_list
    def prog(self):
        dbg_print("parsing PROG")
        sl = self.stmt_list()
        if not self.lexer.EOF():
            raise SyntaxError("expected 'EOF' found '{}'." \
                              .format(self.lexer.peek().type))
        else:
            dbg_print("parsing EOF")
        return sl

    ###########################################################################################
    # stmt_list
    #   : stmt*
    def stmt_list(self):
        dbg_print("parsing STMT_LIST")

        sl = []
        while self.lexer.peek().type in stmt_lookahead:
            sl += [('lineinfo', state.lineinfo)]
            sl += [self.stmt()]
        return ('list', sl)

    ###########################################################################################
    # NOTE: periods are optional at end of sentences but leaving them out can
    #       lead to ambiguities
    # NOTE: the dot is also short hand for the 'noop' command
    #
    # stmt
    #    : '.' // NOOP
    #    | LOAD STRING '.'?
    #    | GLOBAL id_list '.'?
    #    | NONLOCAL id_list '.'?
    #    | ASSERT exp '.'?
    #    | STRUCTURE ID WITH struct_stmts END
    #    | TRAIT ID WITH trait_stmts END
    #    | LET pattern '=' exp '.'?
    #    | LOOP DO? stmt_list END
    #    | FOR pattern IN exp DO stmt_list END
    #    | WHILE exp DO stmt_list END
    #    | REPEAT (DO?) stmt_list UNTIL exp '.'?
    #    | BREAK
    #    | IF exp DO stmt_list (ELIF exp DO stmt_list)* (ELSE (DO?) stmt_list)? END
    #    | RETURN exp? '.'?
    #    | TRY stmt_list (CATCH pattern DO stmt_list)+ END
    #    | THROW exp '.'?
    #    | function_def
    #    | call_or_index '.'?
    def stmt(self):
        dbg_print("parsing STMT")
        tt = self.lexer.peek().type  # tt - Token Type

        if tt == 'DOT':
            self.lexer.match('DOT')
            return ('noop',)

        elif tt == 'LOAD':
            # expand the AST from the file into our current AST
            # using a nested parser object
            self.lexer.match('LOAD')
            sys_flag = bool(self.lexer.match_optional('SYSTEM'))
            str_tok = self.lexer.match('STRING')
            self.lexer.match_optional('DOT')

            raw_pp = PurePath(str_tok.value)
            module_name = raw_pp.stem

            # if module is on the list of modules then we have loaded
            # it already -- ignore -- continue parsing the program file
            if module_name in state.modules:
                # lhh
                # print("Ignoring module {}".format(module_name))
                return self.stmt_list()

            # search for module file:
            # 0. raw module name - could be an absolute path
            # 1. search in current directory (path[1])
            # 2. search in directory where Asteroid is installed (path[0])
            # 3. search in subdirectory where Asteroid was started
            # TODO: does this work on all OS's?
            # TODO: should have an env variable to set search path
            search_list = []
            if not sys_flag:
                search_list.append(str_tok.value)
                search_list.append(str_tok.value + asteroid_file_suffix)
            search_list.append(sys.path[1] + '/' + module_name + asteroid_file_suffix)
            search_list.append(sys.path[1] + '/modules/' + module_name + asteroid_file_suffix)
            search_list.append(sys.path[0] + '/' + module_name + asteroid_file_suffix)
            search_list.append(sys.path[0] + '/modules/' + module_name + asteroid_file_suffix)
            search_list.append('modules/' + module_name + asteroid_file_suffix)

            file_found = False

            for ix in range(len(search_list)):
                ast_module_file = search_list[ix]
                #lhh
                #print("AST module: {}".format(ast_module_file))
                ast_module_path = Path(ast_module_file)
                if ast_module_path.is_file():
                    file_found = True
                    break

            if not file_found:
                raise ValueError("Asteroid module '{}' not found"
                                 .format(str_tok.value))

            #lhh
            #print("opening module {}".format(ast_module_file))

            old_lineinfo = state.lineinfo

            with open(ast_module_file) as f:
                state.modules.append(module_name)
                data = f.read()
                fparser = Parser(module_name)
                (STMT_LIST, fstmts) = fparser.parse(data)

            state.lineinfo = old_lineinfo
            (LIST, sl) = self.stmt_list()
            return ('list', fstmts + sl)

        elif tt == 'GLOBAL':
            dbg_print("parsing GLOBAL")
            self.lexer.match('GLOBAL')
            id_list = self.id_list()
            self.lexer.match_optional('DOT')
            return ('global', id_list)

        elif tt == 'NONLOCAL':
            dbg_print("parsing NONLOCAL")
            self.lexer.match('NONLOCAL')
            id_list = self.id_list()
            self.lexer.match_optional('DOT')
            return ('nonlocal', id_list)

        elif tt == 'ASSERT':
            dbg_print("parsing ASSERT")
            self.lexer.match('ASSERT')
            exp = self.exp()
            self.lexer.match_optional('DOT')
            return ('assert', exp)

        elif tt == 'FUNCTION':
            return self.function_def()

        elif tt == 'STRUCTURE':
            dbg_print("parsing STRUCTURE")
            self.lexer.match('STRUCTURE')
            id_tok = self.lexer.match('ID')
            self.lexer.match('WITH')
            stmts = self.struct_stmts()
            self.lexer.match('END')
            return ('struct-def',
                    ('id', id_tok.value),
                    ('member-list', stmts))

        elif tt == 'LET':
            dbg_print("parsing LET")
            self.lexer.match('LET')
            p = self.pattern()
            self.lexer.match('ASSIGN')
            v = self.exp()
            self.lexer.match_optional('DOT')
            return ('unify', p, v)

        elif tt == 'LOOP':
            dbg_print("parsing LOOP")
            self.lexer.match('LOOP')
            self.lexer.match_optional('DO')
            sl = self.stmt_list()
            self.lexer.match('END')
            #self.lexer.match_optional('LOOP')
            return ('loop',
                    ('stmt-list', sl))

        elif tt == 'FOR':
            dbg_print("parsing FOR")
            self.lexer.match('FOR')
            e = self.exp()
            if e[0] != 'in':
                raise SyntaxError("expected 'in' expression in for loop")
            self.lexer.match('DO')
            sl = self.stmt_list()
            self.lexer.match('END')
            #self.lexer.match_optional('FOR')
            return ('for',
                    ('in-exp', e),
                    ('stmt-list', sl))

        elif tt == 'WHILE':
            dbg_print("parsing WHILE")
            self.lexer.match('WHILE')
            e = self.exp()
            self.lexer.match('DO')
            sl = self.stmt_list()
            self.lexer.match('END')
            #self.lexer.match_optional('WHILE')
            return ('while',
                    ('cond-exp', e),
                    ('stmt-list', sl))

        elif tt == 'REPEAT':
            dbg_print("parsing REPEAT")
            self.lexer.match('REPEAT')
            self.lexer.match_optional('DO')
            sl = self.stmt_list()
            self.lexer.match('UNTIL')
            e = self.exp()
            self.lexer.match_optional('DOT')
            return ('repeat',
                    ('stmt-list', sl),
                    ('until-exp', e))

        elif tt == 'BREAK':
            dbg_print("parsing BREAK")
            self.lexer.match('BREAK')
            return ('break',)

        elif tt == 'IF':
            # if statements are coded as a list of ('if-clause', condition, stmts)
            if_list = []

            dbg_print("parsing IF")
            self.lexer.match('IF')
            cond = self.exp()
            self.lexer.match('DO')
            stmts = self.stmt_list()
            if_list.append(('if-clause', ('cond', cond), ('stmt-list', stmts)))

            while self.lexer.peek().type == 'ELIF':
                dbg_print("parsing ELIF")
                self.lexer.match('ELIF')
                cond = self.exp()
                self.lexer.match('DO')
                stmts = self.stmt_list()
                if_list.append(('if-clause', ('cond', cond), ('stmt-list', stmts)))

            if self.lexer.peek().type == 'ELSE':
                dbg_print("parsing ELSE")
                self.lexer.match('ELSE')
                self.lexer.match_optional('DO')
                stmts = self.stmt_list()
                # make the else look like another elif with the condition set to 'true'
                if_list.append(('if-clause', ('cond', ('boolean', True)), ('stmt-list', stmts)))

            self.lexer.match('END')
            #self.lexer.match_optional('IF')
            return ('if', ('list', if_list))


        elif tt == 'RETURN':
            dbg_print("parsing RETURN")
            self.lexer.match('RETURN')
            if self.lexer.peek().type in exp_lookahead:
                e = self.exp()
                self.lexer.match_optional('DOT')
                return ('return', e)
            else:
                self.lexer.match_optional('DOT')
                return ('return', ('none', None))

        elif tt == 'TRY':
            dbg_print("parsing TRY")

            # the catch list is a list of ('catch', pattern, stmts)
            catch_list = []

            self.lexer.match('TRY')
            try_stmts = self.stmt_list()
            self.lexer.match('CATCH')
            dbg_print("parsing CATCH")
            pattern = self.pattern()
            self.lexer.match('DO')
            stmts = self.stmt_list()
            catch_list.append(('catch', ('pattern', pattern), ('stmt-list', stmts)))

            while self.lexer.peek().type == 'CATCH':
                dbg_print("parsing CATCH")
                self.lexer.match('CATCH')
                pattern = self.pattern()
                self.lexer.match('DO')
                stmts = self.stmt_list()
                catch_list.append(('catch',('pattern', pattern), ('stmt-list', stmts)))

            self.lexer.match('END')
            #self.lexer.match_optional('TRY')

            return ('try',
                    ('stmt-list', try_stmts),
                    ('catch-list', ('list', catch_list)))

        elif tt == 'THROW':
            dbg_print("parsing THROW")
            self.lexer.match('THROW')
            e = self.exp()
            self.lexer.match_optional('DOT')
            return ('throw', e)

        elif tt in primary_lookahead:
            v = self.call_or_index()
            self.lexer.match_optional('DOT')
            return v

        else:
            raise SyntaxError("syntax error at '{}'"
                        .format(self.lexer.peek().value))

    ###########################################################################################
    # function_def
    #  : FUNCTION ID body_defs END FUNCTION
    def function_def(self):
        dbg_print("parsing FUNCTION_DEF")
        self.lexer.match('FUNCTION')
        id_tok = self.lexer.match('ID')
        body_list = self.body_defs()
        self.lexer.match('END')
        #self.lexer.match('FUNCTION')

        # check if any useless patterns exist within the function
        #lhh check_redundancy( body_list, id_tok )

        # functions are function expressions bound to names
        return ('unify',
                ('id',id_tok.value),
                ('function-exp', body_list))

    ###########################################################################################
    # data_stmt
    #  : DATA ID
    def data_stmt(self):
        dbg_print("parsing DATA_STMT")

        if self.lexer.peek().type == 'DATA':
            self.lexer.match('DATA')
            id_tok = self.lexer.match('ID')
            return ('data', ('id', id_tok.value))
        else:
            raise SyntaxError(
                "syntax error at '{}'"
                .format(self.lexer.peek().value))

    ###########################################################################################
    # struct_stmt
    #   : data_stmt '.'?
    #   | function_def '.'?
    #   | '.'
    def struct_stmt(self):
        dbg_print("parsing STRUCT_STMT")

        if self.lexer.peek().type == 'DATA':
            s = self.data_stmt()
            self.lexer.match_optional('DOT')
            return s
        elif self.lexer.peek().type == 'FUNCTION':
            s = self.function_def()
            self.lexer.match_optional('DOT')
            return s
        elif self.lexer.peek().type == 'DOT':
            self.lexer.match('DOT')
            return ('noop',)
        else:
            raise SyntaxError(
                "syntax error at '{}'"
                .format(self.lexer.peek().value))
    ###########################################################################################
    # struct_stmts
    #   : struct_stmt*
    def struct_stmts(self):
        dbg_print("parsing STRUCT_STMTS")

        sl = []
        while self.lexer.peek().type in ['DATA', 'FUNCTION', 'DOT']:
            sl += [self.struct_stmt()]
        return ('list', sl)

    ###########################################################################################
    # id_list
    #   : ID (',' ID)*
    def id_list(self):
        dbg_print("parsing ID_LIST")

        id_list = []

        id_tok = self.lexer.match('ID')
        id_list.append(('id', id_tok.value))
        while self.lexer.peek().type == 'COMMA':
            self.lexer.match('COMMA')
            id_tok = self.lexer.match('ID')
            id_list.append(('id', id_tok.value))
        return ('list', id_list)

    ###########################################################################################
    # body_defs
    #   : WITH pattern DO stmt_list (ORWITH pattern DO stmt_list)*
    def body_defs(self):
        dbg_print("parsing BODY_DEFS")

        # a list of ('body', pattern, stmts) pairs
        body_list = []

        self.lexer.match('WITH')
        p = self.pattern()
        self.lexer.match('DO')
        sl = self.stmt_list()
        body_list.append(('body', ('pattern', p), ('stmt-list', sl)))

        while self.lexer.peek().type == 'ORWITH':
            self.lexer.match('ORWITH')
            p = self.pattern()
            self.lexer.match('DO')
            sl = self.stmt_list()
            body_list.append(('body', ('pattern', p), ('stmt-list', sl)))

        return ('body-list', ('list', body_list))

    ###########################################################################################
    # pattern
    #    : exp
    def pattern(self):
        dbg_print("parsing PATTERN")
        e = self.exp()
        return e

    ###########################################################################################
    # exp
    #    : conditional
    def exp(self):
        dbg_print("parsing EXP")
        v = self.quote_exp()
        return v

    ###########################################################################################
    # quote_exp
    #    : QUOTE exp
    #    | PATTERN WITH? exp
    #    | '%[' exp ']%'
    #    | head_tail
    def quote_exp(self):
        dbg_print("parsing QUOTE_EXP")

        if self.lexer.peek().type == 'QUOTE':
            self.lexer.match('QUOTE')
            v = self.exp()
            return ('quote', v)
        # 'pattern with' is just the long version of the quote char
        elif self.lexer.peek().type == 'PATTERN':
            self.lexer.match('PATTERN')
            self.lexer.match_optional('WITH')
            v = self.exp()
            return ('quote', v)
        elif self.lexer.peek().type == 'LCONSTRAINT': #constraint-only pattern match
            self.lexer.match('LCONSTRAINT')
            v = self.exp()
            self.lexer.match('RCONSTRAINT')
            return ('constraint', v)
        else:
            v = self.head_tail()
            return v

    ###########################################################################################
    # conditional
    #    : quote_exp
    #        (
    #           (CMATCH exp) | // CMATCH == '%'IF
    #           (IF exp ELSE exp) # expression level if-else
    #        )?
    def conditional(self):
        dbg_print("parsing CONDITIONAL")

        v = self.compound()

        tt = self.lexer.peek().type
        if tt == 'CMATCH':
            self.lexer.match('CMATCH')
            e = self.exp()
            return ('cmatch', v, e)

        elif tt == 'IF':
            self.lexer.match('IF')
            v2 = self.exp()
            self.lexer.match('ELSE')
            v3 = self.exp()
            return ('if-exp', v2, v, v3) # mapping it into standard if-then-else format

        else:
            return v

    ###########################################################################################
    # head_tail
    #    : compound ('|' exp)?
    #
    # NOTE: * as a value this operator will construct a list from the semantic values of
    #         head and tail
    #       * as a pattern this operator will be unified with a list such that head will
    #         unify with the first element of the list and tail with the remaining list
    # NOTE: this is a list constructor and therefore should never appear in the semantic
    #       processing, use walk to expand the list before processing it.
    def head_tail(self):
        dbg_print("parsing HEAD_TAIL")

        v = self.conditional()

        if self.lexer.peek().type == 'BAR':
            self.lexer.match('BAR')
            head = v
            tail = self.exp()
            v = ('raw-head-tail', head, tail)

        return v

    ###########################################################################################
    # compound
    #    : logic_exp0
    #        (
    #           (IS pattern) |
    #           (IN exp) | // exp has to be a list
    #           (TO exp (STEP exp)?) | // list comprehension
    #        )?
    def compound(self):
        dbg_print("parsing COMPOUND")

        v = self.logic_exp0()

        tt = self.lexer.peek().type
        if tt == 'IS':
            self.lexer.match('IS')
            v2 = self.pattern()
            return ('is', v, v2)

        elif tt == 'IN':
            self.lexer.match('IN')
            v2 = self.exp()
            return ('in', v, v2)

        elif tt == 'TO':
            self.lexer.match('TO')
            v2 = self.exp()
            if self.lexer.peek().type == 'STEP':
                self.lexer.match('STEP')
                v3 = self.exp()
                return ('raw-to-list',
                        ('start', v),
                        ('stop', v2),
                        ('step', v3))
            else:
                return ('raw-to-list',
                        ('start', v),
                        ('stop', v2),
                        ('step', ('integer', '1')))

        else:
            return v

    ###########################################################################################
    # NOTE: Builtin operators are mapped to 'apply' so that they don't have to be
    #       special cased during pattern matching.  See operator_symbols above.
    ###########################################################################################
    # logic/relational/arithmetic operators with their precedence
    # logic_exp0
    #   : logic_exp1 (OR logic_exp1)*
    #
    # logic_exp1
    #   : rel_exp1 (AND rel_exp1)*
    #
    # rel_exp0
    #   : rel_exp1 (('==' | '=/=' /* not equal */) rel_exp1)*
    #
    # rel_exp1
    #   : arith_exp0 (('<=' | '<'  | '>=' | '>') arith_exp0)*
    #
    # arith_exp0
    #   : arith_exp1 (('+' | '-') arith_exp1)*
    #
    # arith_exp1
    #   : call_or_index (('*' | '/') call_or_index)*
    #
    def logic_exp0(self):
        dbg_print("parsing LOGIC/REL/ARITH EXP")
        v = self.logic_exp1()
        while self.lexer.peek().type == 'OR':
            self.lexer.match('OR')
            v2 = self.logic_exp1()
            op_sym = '__or__'
            v = ('apply', ('id', op_sym), ('tuple', [v, v2]))
        return v

    def logic_exp1(self):
        v = self.rel_exp0()
        while self.lexer.peek().type == 'AND':
            self.lexer.match('AND')
            v2 = self.rel_exp0()
            op_sym = '__and__'
            v = ('apply', ('id', op_sym), ('tuple', [v, v2]))
        return v

    def rel_exp0(self):
        v = self.rel_exp1()
        while self.lexer.peek().type in ['EQ', 'NE']:
            op_tok = self.lexer.peek()
            self.lexer.next()
            v2 = self.rel_exp1()
            op_sym = '__' + op_tok.type.lower() + '__'
            v = ('apply', ('id', op_sym), ('tuple', [v, v2]))
        return v

    def rel_exp1(self):
        v = self.arith_exp0()
        while self.lexer.peek().type in ['LE', 'LT', 'GE', 'GT']:
            op_tok = self.lexer.peek()
            self.lexer.next()
            v2 = self.arith_exp0()
            op_sym = '__' + op_tok.type.lower() + '__'
            v = ('apply', ('id', op_sym), ('tuple', [v, v2]))
        return v

    def arith_exp0(self):
        dbg_print("parsing ARITH_EXP")
        v = self.arith_exp1()
        while self.lexer.peek().type in ['PLUS', 'MINUS']:
            op_tok = self.lexer.peek()
            self.lexer.next()
            v2 = self.arith_exp1()
            op_sym = '__' + op_tok.type.lower() + '__'
            v = ('apply', ('id', op_sym), ('tuple', [v, v2]))
        return v

    def arith_exp1(self):
        v = self.call_or_index()
        while self.lexer.peek().type in ['TIMES', 'DIVIDE']:
            op_tok = self.lexer.peek()
            self.lexer.next()
            v2 = self.call_or_index()
            op_sym = '__' + op_tok.type.lower() + '__'
            v = ('apply', ('id', op_sym), ('tuple', [v, v2]))
        return v

    ###########################################################################################
    # call_or_index
    #   : primary (primary | '@' primary)*
    def call_or_index(self):
        dbg_print("parsing CALL_OR_INDEX")

        v = self.primary()

        # Note: the 'no ops' lookahead here is necessary because operators
        # can never be arguments to a function in Asteroid
        call_or_index_lookahead = primary_lookahead_no_ops|set(['AT'])
        while self.lexer.peek().type in call_or_index_lookahead:
            if self.lexer.peek().type in primary_lookahead:
                v2 = self.primary()
                v = ('apply', v, v2)
            elif self.lexer.peek().type == 'AT':
                self.lexer.match('AT')
                ix = self.primary()
                v = ('index', v, ix)

        return v

    ###########################################################################################
    # primary
    #    : INTEGER
    #    | REAL
    #    | STRING
    #    | TRUE
    #    | FALSE
    #    | NONE
    #    | ID (':' pattern)?  // named pattern when ': pattern' exists
    #    | '*' ID         // "dereference" a variable during pattern matching
    #    | NOT call_or_index
    #    | MINUS call_or_index
    #    | ESCAPE STRING
    #    | EVAL exp
    #    | '(' tuple_stuff ')' // tuple/parenthesized expr
    #    | '[' list_stuff ']'  // list or list access
    #    | function_const
    #    | TYPEMATCH // TYPEMATCH == '%'<typename>
    def primary(self):
        dbg_print("parsing PRIMARY")

        tt = self.lexer.peek().type

        if tt == 'INTEGER':
            tok = self.lexer.match('INTEGER')
            return ('integer', tok.value)

        elif tt == 'REAL':
            tok = self.lexer.match('REAL')
            return ('real', tok.value)

        elif tt == 'STRING':
            tok = self.lexer.match('STRING')
            return ('string', tok.value)

        elif tt == 'TRUE':
            self.lexer.match('TRUE')
            return ('boolean', True)

        elif tt == 'FALSE':
            self.lexer.match('FALSE')
            return ('boolean', False)

        elif tt == 'NONE':
           self.lexer.match('NONE')
           return ('none', None)

        elif tt == 'ID':
            tok = self.lexer.match('ID')
            if self.lexer.peek().type == 'COLON': # if ':' exists - named pattern
                self.lexer.match('COLON')
                v = self.exp()
                return ('named-pattern',
                        ('id', tok.value),
                        v)
            else:
                return ('id', tok.value)

        elif tt == 'TIMES':
            self.lexer.match('TIMES')
            id_tok = self.lexer.match('ID')
            return ('deref', ('id', id_tok.value))

        elif tt == 'NOT':
            self.lexer.match('NOT')
            v = self.call_or_index()
            return ('apply', ('id', '__not__'), v)

        elif tt == 'MINUS':
            self.lexer.match('MINUS')
            v = self.call_or_index()
            # if v is a real or integer constant we apply __uminus__
            if v[0] in ['integer', 'real']:
                return (v[0], - v[1])
            else:
                return ('apply', ('id', '__uminus__'), v)

        elif tt == 'ESCAPE':
            self.lexer.match('ESCAPE')
            str_tok = self.lexer.match('STRING')
            return ('escape', str_tok.value)

        elif tt == 'EVAL':
            self.lexer.match('EVAL')
            exp = self.primary()
            return ('eval', exp)

        elif tt == 'LPAREN':
            # Parenthesized expressions have the following meaning:
            #       (A)    means a parenthesized value A
            #       (A,)   means a tuple with a single value A
            #       (A, B) means a tuple with values A and B
            #       ()     shorthand for 'none'
            self.lexer.match('LPAREN')
            v = self.tuple_stuff()
            self.lexer.match('RPAREN')
            return v

        elif tt == 'LBRACKET':
            self.lexer.match('LBRACKET')
            v = self.list_stuff()
            self.lexer.match('RBRACKET')
            return v

        elif tt == 'LAMBDA':
            return self.function_const()

        elif tt == 'TYPEMATCH':
            tok = self.lexer.match('TYPEMATCH')
            return ('typematch', tok.value)

        else:
            raise SyntaxError(
                "syntax error at '{}'"
                .format(self.lexer.peek().value))

    ###########################################################################################
    # tuple_stuff
    #   : exp (',' exp?)*
    #   | empty
    def tuple_stuff(self):
        dbg_print("parsing TUPLE_STUFF")
        if self.lexer.peek().type in exp_lookahead:
            v = self.exp()
            if self.lexer.peek().type == 'COMMA': # if ',' exists - tuple!
                tuple_list = [v]
                while self.lexer.peek().type == 'COMMA':
                    self.lexer.match('COMMA')
                    if self.lexer.peek().type in exp_lookahead:
                        e = self.exp()
                        tuple_list.append(e)
                return ('tuple', tuple_list)

            else: # just parenthesized value - drop parentheses
                return v
        else:
            # empty parentheses are a shorthand for 'none'
            return ('none', None)

    ###########################################################################################
    # list_stuff
    #   : exp (',' exp)*
    #   | empty
    def list_stuff(self):
        dbg_print("parsing LIST_STUFF")
        if self.lexer.peek().type in exp_lookahead:
            v = self.exp()
            if v[0] == 'raw-to-list':
                return ('to-list', v[1], v[2], v[3])
            elif v[0] == 'raw-head-tail':
                return ('head-tail', v[1], v[2])
            elif self.lexer.peek().type == 'COMMA': # if ',' exists - list!
                list_list = [v]
                while self.lexer.peek().type == 'COMMA':
                    self.lexer.match('COMMA')
                    e = self.exp()
                    list_list.append(e)
                return ('list', list_list)
            else:
                return ('list', [v])
        else:
            return ('list', [])

    ###########################################################################################
    # function_const
    #    : LAMBDA body_defs
    def function_const(self):
        dbg_print("parsing FUNCTION_CONST")
        self.lexer.match('LAMBDA')
        body_list = self.body_defs()

        return ('function-exp', body_list)

import re

from rply import ParserGenerator, LexerGenerator
from rply.lexergenerator import Lexer
from rply.parsergenerator import LRParser

from pydice import D


def _build_parser() -> (LRParser, Lexer):
    lg = LexerGenerator()

    lg.add('PLUS', r'\+')
    lg.add('MINUS', r'-')
    lg.add('DICE', r'[d|D]\d+')
    lg.add('NDICE', r'\d+[d|D]\d+')
    lg.add('NUMBER', r'\d+')
    lg.ignore(r'\s+')

    pg = ParserGenerator(tokens=['NDICE', 'DICE', 'NUMBER', 'PLUS', 'MINUS'],
                         precedence=[('left', ['NDICE', 'DICE', 'NUMBER', 'PLUS', 'MINUS'])],
                         cache_id='pydice_parser')

    @pg.production('main : expr')
    def main(p):
        return p[0]

    @pg.production('expr : expr PLUS expr')
    @pg.production('expr : expr MINUS expr')
    def expr_add_subtract(p):
        lhs = p[0]
        rhs = p[2]
        if p[1].gettokentype() == 'PLUS':
            return lhs + rhs
        elif p[1].gettokentype() == 'MINUS':
            return lhs - rhs
        else:
            raise AssertionError('No matching operator found!')

    @pg.production('expr : MINUS expr')
    def expr_unary_negative(p):
        rhs = p[1]
        return rhs.negate

    @pg.production('expr : PLUS expr')
    def expr_unary_positive(p):
        return p[1]

    @pg.production('expr : DICE')
    def expr_dice(p):
        return D(int(p[0].getstr()[1:]))

    @pg.production('expr : NDICE')
    def expr_ndice(p):
        n, d = re.split(r'[d|D]', p[0].getstr())
        return int(n) * D(int(d))

    @pg.production('expr : NUMBER')
    def expr_number(p):
        return D.fixed(int(p[0].getstr()))

    @pg.error
    def handle_parse_error(token):
        raise ValueError('Invalid dice format string, found a {} where not expected'.format(token.gettokentype()))

    return pg.build(), lg.build()


_p, _l = _build_parser()


def parse(value: str) -> D:
    """
    Parse a standard dice string such as 'd4+5' or '2d20+4d6-2' and produce the corresponding distribution.

    :param value:
        A string to parse
    :return:
        The probability distribution of the parsed dice set
    """
    return _p.parse(_l.lex(value))

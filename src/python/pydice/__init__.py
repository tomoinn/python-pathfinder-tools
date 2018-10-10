import copy
import fractions
import re
from random import random

from rply import ParserGenerator, LexerGenerator
from rply.lexergenerator import Lexer
from rply.parsergenerator import LRParser


class D:
    """
    Represents a set of integers with associated probabilities as Fraction objects

    These can be added, in which case the result is a new distribution representing the results of rolling each
    distribution and adding the values. They can also be multiplied by a positive integer value, in which case this is
    equivalent to repeatedly adding the distribution to itself (with multiplication by 0 resulting in a flat
    distribution of 0 with probability one). Adding an integer is treated as equivalent to adding a flat distribution,
    and coercion to fixed distributions happens automatically, so you can do e.g. D(6)+1 to get the distribution
    corresponding to rolling a six sided dice and adding one, or you can do either D(6)+D(6) or D(6)*2 to get the result
    of rolling two six sided dice and adding the values rolled.

    Instances of this class can either be constructed with a dict of int -> Fraction, in which case the dict is copied
    and used as the internal map of values to probabilities, or through the convenience method that takes an integer and
    constructs a probability distribution with n values from 1 to n with even probabilities. This is equivalent to the
    distribution of a dice with n sides, so D(6) is a regular six sided dice and so on. In addition, a string can be
    supplied with the same format as used by pydice.parser.parse, i.e. '3d6+d8-7' or similar.
    """

    def __init__(self, distribution: {}, check_probabilities_sum_to_one=True):
        """
        Create a new distribution

        :param distribution:
            A dict where keys are integers, and values are Fraction objects representing the probability of that integer
            being 'rolled' in a random pick from the distribution. Alternative, specify an int to create a flat dice
            distribution with values between 1 and the specified value, or a string containing a parseable dice format.
        """
        if isinstance(distribution, int):
            self.__dict = {value + 1: fractions.Fraction(1, distribution) for value in range(distribution)}
        elif isinstance(distribution, str):
            self.__dict = parse(distribution).__dict
        else:
            self.__dict = copy.deepcopy(distribution)

        # Remove any zero probability values as they interfere with min / max properties
        self.__dict = {v: self.__dict[v] for v in self.__dict if self.__dict[v] > 0}

        # Check that probabilities sum to 1 if not supressing checks
        if check_probabilities_sum_to_one and sum([self.__dict[a] for a in self.__dict]) != 1:
            raise ValueError('Probabilities in distribution must sum to 1')

        self.__cumulative = []
        __c = 0
        for value in sorted(self.__dict):
            __c += self.__dict[value]
            self.__cumulative.append((value, __c))

    @property
    def max(self) -> int:
        """
        The highest value in the distribution
        """
        return max(self.__dict)

    @property
    def min(self) -> int:
        """
        The lowest value in the distribution
        """
        return min(self.__dict)

    @property
    def dist(self) -> {}:
        """
        Creates and returns a deep copy of the internal distribution dictionary of value -> fraction
        """
        return copy.deepcopy(self.__dict)

    @property
    def cumulative(self) -> {}:
        """
        Creates and returns a deep copy of the internal cumulative distribution of value -> fraction
        """
        return copy.deepcopy(self.__cumulative)

    def roll(self, n=1):
        """
        Returns an array of length n containing n 'rolls' from this distribution

        :param n:
            The number of rolls needed
        :return:
            An array of the requested size containing rolls of the distribution
        """
        return list([self.r for _ in range(n)])

    @property
    def r(self):
        """
        Return a single roll of the distribution

        :return:
            An int value from a single roll
        """
        r = random()
        for v, p in self.__cumulative:
            if p >= r:
                return v

    @staticmethod
    def fixed(value: int) -> 'D':
        """
        Create a new distribution with a single possible value at probability one.

        :param value:
            The value to use as the single possible return from this distribution
        :return:
            The resultant fixed distribution
        """
        return D(distribution={value: fractions.Fraction(1, 1)})

    @staticmethod
    def sub(a: 'D', b: 'D') -> 'D':
        """
        Subtract one distribution from another. This creates a new distribution which represents the results of adding
        the values rolled by the first distribution to those rolled by the second multiplied by -1. For example, a d6-d4
        distribution would contain values from -3 to 5. Used by __sub__ and __rsub__ methods, it's almost certainly
        easier to use those with regular subtraction than calling this function.

        :param a:
            Positive distribution
        :param b:
            Negative distribution
        :return:
            The sum of the two distributions, with the second being negated before adding.
        """
        return D.add(a, b.negate)

    @staticmethod
    def add(a: 'D', b: 'D') -> 'D':
        """
        Add two distributions to create a new one representing the distribution created by independently 'rolling' each
        of the inputs and adding the values together. This is used by the __add__ and __radd__ as well as __mul__ and
        __rmul__

        :param a:
            A distribution to add
        :param b:
            The other distribution to add
        :return:
            The derived distribution
        """
        d = {}
        for va, pa in a.__dict.items():
            for vb, pb in b.__dict.items():
                value = va + vb
                prob = pa * pb
                if value in d:
                    d[value] = d[value] + prob
                else:
                    d[value] = prob
        return D(distribution=d)

    @property
    def negate(self) -> 'D':
        """
        Return a distribution where all the values are negative versions of those in this distribution
        """
        return D(distribution={-v: self.__dict[v] for v in self.__dict})

    @property
    def mean(self) -> fractions.Fraction:
        """
        Calculate the mean, defined as the sum of products of values and probabilities for all values in the dict. As
        all probabilities are expressed as fractions this is a fraction.

        :return:
            The mean as a Fraction object
        """
        return sum([key * self.__dict[key] for key in self.__dict])

    @property
    def float_mean(self) -> float:
        """
        As with the mean, but coercing to a float for convenience

        :return:
            The mean as a float
        """
        return float(self.mean)

    def p(self, min=None, max=None) -> fractions.Fraction:
        """
        Return the probability, as a Fraction, of a given range of values.

        :param min:
            The minimum allowed value, defaulting to None to not specify a lower bouond
        :param max:
            The maximum allowed value, defaulting to None to not specify an upper bound
        :return:
            The probability of a single 'roll' of this distribution returning a value in the specified range, defined
            as a Fraction
        """

        def check(value):
            if min is not None and value < min:
                return False
            if max is not None and value > max:
                return False
            return True

        return sum([self.__dict[value] for value in self.__dict if check(value)])

    def __scale(self, s) -> 'D':
        """
        Scales all the probability values by the specified value, which can be either a float or, preferably, a Fraction
        object. This returns a new distribution which won't really make sense in itself as its probability values won't
        actually add up to one. This is really only used with the pick function.

        :param s:
            A float or Fraction value by which all probabilities in the distribution should be scaled
        :return:
            A new distribution containing the scaled probabilities
        """
        if not isinstance(s, fractions.Fraction):
            s = fractions.Fraction(s)
        return D(distribution={value: self.__dict[value] * s for value in self.__dict},
                 check_probabilities_sum_to_one=False)

    @staticmethod
    def pick(l: []) -> 'D':
        """
        Create and return a new distribution representing the results of picking exactly one of a set of distributions
        with associated probabilities. These are specified as a list of tuples, where each tuple is a (distribution, p)
        pair. The p values should sum to 1 across the entire list, a ValueError is raised otherwise.

        This is used to represent choice points, such as using a different distribution to represent miss damage, hit
        damage, or critical damage with probabilities for selecting each one.

        :param l:
            A list of (distribution, p) tuples representing mutually exclusive choices
        :return:
            The resultant distribution from that list of possible choices and probabilities
        """

        def dist_for(item):
            if isinstance(item, int):
                return D.fixed(item)
            elif isinstance(item, str):
                return D(item)
            else:
                return item

        if sum([b for a, b in l]) != 1:
            raise ValueError('Probabilities in pick must sum to 1')

        d = {}
        for (a, b) in l:
            a = dist_for(a).__scale(b)
            for value in a.__dict:
                prob = a.__dict[value]
                if value in d:
                    d[value] = d[value] + prob
                else:
                    d[value] = prob
        return D(distribution=d)

    def extract(self, min=None, max=None) -> 'D':
        """
        Extract a range of values from this distribution and copy them into a new one, scaling probabilities such that
        those in the result sum to 1. This can be used for bayesian operations where, given that we know a result range,
        we want to know the relative probabilities of results within that range.

        :param min:
            The minimum value to pick from the distribution, defaults to None for no minimum
        :param max:
            The maximum value to pick from the distribution, defaults to None for no maximum
        :return:
            The extracted distribution
        """

        def check(value):
            if min is not None and value < min:
                return False
            if max is not None and value > max:
                return False
            return True

        new_dist = D(distribution={v: self.__dict[v] for v in self.__dict if check(v)},
                     check_probabilities_sum_to_one=False)
        if len(new_dist.__dict) == 0:
            # If there are no items we can't normalise, so return a fixed 0 distribution
            return D.fixed(0)
        return new_dist.__scale(1 / new_dist.p())

    def __add__(self, other):
        if isinstance(other, int):
            return D.add(self, D.fixed(value=other))
        return D.add(self, other)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, int):
            return D.sub(self, D.fixed(value=other))
        return D.sub(self, other)

    def __rsub__(self, other):
        if isinstance(other, int):
            return D.sub(D.fixed(value=other), self)
        return D.sub(other, self)

    def __mul__(self, other):
        if not isinstance(other, int):
            raise ValueError('Can only multiply a distribution with an integer.')
        if other == 0:
            return D.fixed(value=0)
        if other < 0:
            raise ValueError('Cannot multiply a distribution by a negative integer.')
        if other == 1:
            return self
        else:
            return self + self * (other - 1)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __repr__(self):
        return '[' + ', '.join(
            '{}:{}/{}'.format(key, self.__dict[key].numerator, self.__dict[key].denominator) for key in
            sorted(self.__dict)) + ']'

    def __len__(self):
        """
        The number of values in the distribution
        """
        return len(self.__dict)


def _build_parser() -> (LRParser, Lexer):
    """
    Build the parser and lexer for the dice format string, i.e. '3d6-d5+2'

    :return:
        A tuple of LRParser, Lexer for this format
    """
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


def parse(value: str) -> 'D':
    """
    Parse a standard dice string such as 'd4+5' or '2d20+4d6-2' and produce the corresponding distribution.

    :param value:
        A string to parse
    :return:
        The probability distribution of the parsed dice set
    """
    return _p.parse(_l.lex(value))

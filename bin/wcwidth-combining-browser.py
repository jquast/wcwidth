browser = __import__('wcwidth-browser')
import string
import unicodedata
from wcwidth import wcwidth, table_comb


class WcCombinedCharacterGenerator(object):
    def __init__(self, width=1):
        self.characters = []
        for boundaries in table_comb.NONZERO_COMBINING:
            for i in range(boundaries[0], boundaries[1]+1):
                self.characters.append(u'o' + browser.unichr(i))
        self.characters.reverse()

    def __next__(self):
        while True:
            if not self.characters:
                raise StopIteration
            ucs = self.characters.pop()
            try:
                name = string.capwords(unicodedata.name(ucs[1]))
            except ValueError:
                continue
            return (ucs, name)
    
    # python 2.6 - 3.3 compatibility
    next = __next__


if __name__ == '__main__':
    browser.main(WcCombinedCharacterGenerator)


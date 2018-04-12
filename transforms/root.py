import re

prefix_re = re.compile('^(GST\-|FLAG\-|Flag\-|FLAG\:|Flag\:|v\-|V\-|c\-|C\-|p\-|P\-)')
suffix_re = re.compile('(\-p|\-P|\-GDP|\-GTP|\-ATP|\-ADP|\-dependent|\-independent|\-WT|\-wildtype|\-mutant)$')
plural_re = re.compile('s$')

def root(word):
    result = set()
    result.add(prefix_re.sub("", word))
    result.add(suffix_re.sub("", word))
    singular = plural_re.sub("", word)
    # Only add words of 3 or more characters in length *after* removal of plural 's' to avoid many false positives
    if len(singular) > 2:
        result.add(singular)
    return list(result)
